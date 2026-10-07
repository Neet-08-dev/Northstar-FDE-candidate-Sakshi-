"""Business actions return confirmed outcomes; the model supplies candidates only."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from .backend import Backend, BackendError, Record, operation_key

SAFETY_REPLY = "Move away from the hazard and contact site emergency personnel. Routine service requires safety clearance."


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["schedule", "clarify", "hazard", "unsupported"]
    ticket_id: str = Field(default="", max_length=100)
    site_id: str = Field(default="", max_length=100)
    asset_id: str = Field(default="", max_length=100)
    time_mode: Literal["earliest", "exact", "unclear"] = "unclear"
    starts_at: str = Field(default="", max_length=80)
    clarification: Literal["identity", "time", "intent"] = "identity"


@dataclass(frozen=True)
class Outcome:
    status: str
    reply: str


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Explicit timezone required")
    return parsed.astimezone(timezone.utc)


def display_time(value: str) -> str:
    local = utc(value).astimezone(ZoneInfo("Asia/Kolkata"))
    return f"{local.day} {local:%B %Y, %H:%M} IST (UTC+05:30)"


def clarification(reason: str) -> Outcome:
    questions = {
        "identity": "Please confirm the ticket ID and site or asset for the service visit.",
        "time": "Please confirm the date, time and timezone, or authorize the earliest available qualified slot.",
        "intent": "Would you like me to book a service visit for an existing ticket? Please confirm the ticket ID.",
    }
    return Outcome("needs_clarification", questions[reason])


class Actions:
    def __init__(self, backend: Backend, context: Record, policy: Record):
        self.backend, self.context, self.policy = backend, context, policy
        self.request_id = context["request_id"]

    async def handoff(self, queue: str, reason: str, ticket_id: str = "") -> Outcome:
        args = {"queue": queue, "reason": reason}
        if ticket_id:
            args["ticket_id"] = ticket_id
        prefix = SAFETY_REPLY + " " if queue == "safety" else ""
        try:
            row = await self.backend.call(
                "escalate",
                recovery=True,
                **args,
                idempotency_key=operation_key(self.request_id, "escalate", args),
            )
            self.backend.remember("escalations", row["id"])
            return Outcome(
                "escalated", prefix + f"{reason} A {queue} handoff is recorded as {row['id']}."
            )
        except BackendError:
            return Outcome(
                "error",
                prefix
                + "The requested work could not be confirmed, and the human handoff could not be confirmed. Please contact operations directly.",
            )

    async def handle(self, decision: Decision) -> Outcome:
        if decision.intent == "hazard":
            return await self.handoff(
                "safety", "A possible emergency requires immediate human safety review."
            )
        if not self.context["actor"].get("verified"):
            return await self.handoff(
                "identity", "Requester identity must be verified before accessing service records."
            )
        if decision.intent == "clarify":
            return clarification(decision.clarification)
        if decision.intent == "unsupported":
            return await self.handoff(
                "operations",
                "This assistant currently books visits for existing tickets. This request needs human review.",
            )
        if self.context["actor"].get("role") not in {"customer", "dispatcher", "supervisor"}:
            return Outcome("blocked", "Your current role is not authorized to schedule service.")
        if not decision.ticket_id:
            return clarification("identity")
        if decision.time_mode == "unclear":
            return clarification("time")
        if decision.time_mode == "exact":
            try:
                utc(decision.starts_at)
            except (ValueError, TypeError):
                return clarification("time")
        try:
            return await self.schedule_service(decision)
        except BackendError as exc:
            if exc.code in {"RECORD_UNAVAILABLE", "FORBIDDEN", "UNVERIFIED"}:
                return Outcome(
                    "blocked",
                    "The requested record is unavailable within your authorized account. Please confirm the reference or contact operations for access verification.",
                )
            return await self.handoff(
                "operations",
                "Scheduling could not be confirmed because a tool was unavailable or live state changed. Operations must reconcile any uncertain booking before retrying.",
            )
        except (KeyError, ValueError, TypeError):
            return await self.handoff(
                "operations",
                "Current service records or policy need reconciliation before a booking can be confirmed.",
            )

    async def _eligible(
        self, decision: Decision
    ) -> tuple[Record, Record, Record, list[Record]] | Outcome:
        b = self.backend
        ticket = await b.record("tickets", decision.ticket_id)
        asset = await b.record("assets", ticket["asset_id"])
        site = await b.record("sites", ticket["site_id"])
        customer_ids = self.context["actor"]["customer_ids"]
        if any(row["customer_id"] not in customer_ids for row in [ticket, asset, site]):
            return Outcome("blocked", "The requested records are outside your authorized account.")
        if (
            len({row["customer_id"] for row in [ticket, asset, site]}) != 1
            or asset["site_id"] != site["id"]
        ):
            return await self.handoff(
                "operations", "Current ticket, asset and site identity records conflict."
            )
        if (decision.site_id and decision.site_id != site["id"]) or (
            decision.asset_id and decision.asset_id != asset["id"]
        ):
            return clarification("identity")
        if asset.get("safety_hold") or ticket.get("severity") == "S1":
            return await self.handoff(
                "safety", "The asset or ticket requires safety clearance.", ticket["id"]
            )
        if asset["status"] != "active" or site["status"] != "active":
            return await self.handoff(
                "operations",
                "The asset or site is inactive and requires reconciliation.",
                ticket["id"],
            )
        if ticket["status"] not in {"open", "in_progress"}:
            return Outcome(
                "blocked",
                "This ticket is resolved or unavailable for scheduling. No visit was booked.",
            )
        customer = await b.record("customers", site["customer_id"])
        if customer["account_status"] != "active":
            return await self.handoff(
                "operations",
                "The account needs review before service can be scheduled.",
                ticket["id"],
            )
        self.policy = await b.call("get_policy")
        b.remember("policy", self.policy["rules"]["version"])
        rules = self.policy["rules"]["scheduling"]
        if rules.get("duration_minutes") != 60 or any(
            rules.get(k) is not True
            for k in ["require_skill", "require_region", "require_safety_clearance"]
        ):
            return await self.handoff(
                "operations", "The current scheduling policy needs human review.", ticket["id"]
            )
        now = utc(self.context["now"]).date().isoformat()
        contracts = [
            c
            for c in await b.search("contracts", site["id"])
            if c["customer_id"] == site["customer_id"]
            and site["id"] in c["site_ids"]
            and c["status"] == "active"
            and c["starts_at"] <= now <= c["ends_at"]
            and asset["required_skill"] in c["covered_skills"]
        ]
        if not contracts:
            return await self.handoff(
                "operations",
                "Service coverage is unavailable or expired. Operations must quote or reconcile coverage.",
                ticket["id"],
            )
        return ticket, asset, site, contracts

    @staticmethod
    def _within_access(site: Record, starts_at: str) -> bool:
        match = re.fullmatch(r"(\d{2}:\d{2})-(\d{2}:\d{2})(?: (UTC))?", site["access_window"])
        if not match:
            return False
        zone = ZoneInfo("UTC" if match[3] else site["timezone"])
        start = utc(starts_at).astimezone(zone)
        end = start + timedelta(hours=1)
        return (
            start.date() == end.date()
            and match[1] <= start.strftime("%H:%M")
            and end.strftime("%H:%M") <= match[2]
        )

    async def schedule_service(self, decision: Decision) -> Outcome:
        b = self.backend
        # A conflict may justify one fresh investigation, never a blind write replay.
        for replan in range(2):
            eligible = await self._eligible(decision)
            if isinstance(eligible, Outcome):
                return eligible
            ticket, asset, site, contracts = eligible
            existing = [
                v for v in await b.search("visits", ticket["id"]) if v["ticket_id"] == ticket["id"]
            ]
            if existing:
                visit = existing[0]
                if len(existing) != 1 or visit.get("status") != "scheduled":
                    return await self.handoff(
                        "operations", "Existing visit records need reconciliation.", ticket["id"]
                    )
                if decision.time_mode == "exact" and utc(visit["starts_at"]) != utc(
                    decision.starts_at
                ):
                    return Outcome(
                        "needs_clarification",
                        f"Ticket {ticket['id']} already has a visit at {display_time(visit['starts_at'])}. Please confirm whether you want operations to reschedule it.",
                    )
                return self._booked(ticket["id"], visit, existing=True)
            slots = (await b.call("list_slots", asset_id=asset["id"]))["slots"]
            candidates = []
            for slot in slots:
                start = utc(slot["starts_at"])
                if (
                    slot.get("duration_minutes") == 60
                    and start > utc(self.context["now"])
                    and self._within_access(site, slot["starts_at"])
                    and any(
                        c["starts_at"] <= start.date().isoformat() <= c["ends_at"]
                        for c in contracts
                    )
                ):
                    candidates.append(slot)
            candidates.sort(key=lambda s: (utc(s["starts_at"]), s["technician_id"]))
            if decision.time_mode == "exact":
                matching = [s for s in candidates if utc(s["starts_at"]) == utc(decision.starts_at)]
                if not matching and candidates:
                    return Outcome(
                        "needs_clarification",
                        f"The requested time is unavailable. Would {display_time(candidates[0]['starts_at'])} work instead? No new visit was booked.",
                    )
                candidates = matching
            if not candidates:
                return await self.handoff(
                    "operations", "No eligible one-hour technician slot is available.", ticket["id"]
                )
            slot = candidates[0]
            tech = await b.record("technicians", slot["technician_id"])
            if not (
                tech["active"]
                and tech["region"] == site["region"]
                and asset["required_skill"] in tech["skills"]
                and any(utc(s) == utc(slot["starts_at"]) for s in tech["available_slots"])
            ):
                return await self.handoff(
                    "operations",
                    "Technician eligibility changed; dispatch must reconcile availability.",
                    ticket["id"],
                )
            args = {
                "ticket_id": ticket["id"],
                "technician_id": tech["id"],
                "starts_at": slot["starts_at"],
            }
            try:
                visit = await b.call(
                    "schedule_visit",
                    **args,
                    idempotency_key=operation_key(self.request_id, "schedule_visit", args),
                )
                b.remember("visits", visit["id"])
                return self._booked(ticket["id"], visit)
            except BackendError as exc:
                if replan == 0 and exc.code in {
                    "SLOT_UNAVAILABLE",
                    "VERSION_CONFLICT",
                    "ALREADY_SCHEDULED",
                }:
                    continue
                raise
        raise BackendError("CONFLICT_UNRESOLVED")

    @staticmethod
    def _booked(ticket_id: str, visit: Record, existing: bool = False) -> Outcome:
        lead = "Already scheduled" if existing else "Booked"
        return Outcome(
            "completed",
            f"{lead}: ticket {ticket_id}, visit {visit['id']}, technician {visit['technician_id']}, at {display_time(visit['starts_at'])} for one hour. Repair completion is not yet confirmed.",
        )
