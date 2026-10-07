"""Business actions return confirmed outcomes; the model supplies candidates only."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from .backend import Backend, BackendError, Record

SAFETY_REPLY = "Move away from the hazard and contact site emergency personnel. Routine service requires safety clearance."


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["schedule", "intake", "credit", "clarify", "hazard", "unsupported"]
    ticket_id: str = Field(default="", max_length=100)
    site_id: str = Field(default="", max_length=100)
    asset_id: str = Field(default="", max_length=100)
    time_mode: Literal["earliest", "exact", "unclear"] = "unclear"
    starts_at: str = Field(default="", max_length=80)
    clarification: Literal[
        "identity", "time", "intent", "issue", "conditional", "invoice", "amount", "mixed"
    ] = "identity"
    intake_mode: Literal["record_only", "record_and_schedule"] = "record_only"
    issue_category: Literal["interruption", "maintenance", "unclear"] = "unclear"
    issue_summary: str = Field(default="", max_length=500)
    invoice_id: str = Field(default="", max_length=100)
    amount_cents: int | None = Field(default=None, strict=True)
    currency: Literal["USD", "unsupported"] = "USD"


@dataclass(frozen=True)
class Outcome:
    status: str
    reply: str


def operation_key(request_id: str, tool: str, arguments: Record) -> str:
    content = json.dumps([request_id, tool, arguments], sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def dollars(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


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
        "invoice": "Please identify the invoice or service ticket for the credit.",
        "amount": "What exact amount in USD would you like credited? Please use whole cents and a positive amount.",
        "mixed": "Would you like me to handle the credit request or the service request first? No action has been taken.",
        "identity": "Please confirm the ticket ID, or the site and asset needing service.",
        "issue": "Please describe whether equipment has stopped working or needs nonurgent maintenance.",
        "conditional": "Creating a ticket and booking a visit are separate actions. May I retain the ticket if booking cannot be completed?",
        "time": "Please confirm the date, time and timezone, or authorize the earliest available qualified slot.",
        "intent": "Would you like me to record a service ticket, book a visit, or request a service credit? Please confirm the action and relevant site, equipment, ticket or invoice.",
    }
    return Outcome("needs_clarification", questions[reason])


class Actions:
    def __init__(self, backend: Backend, context: Record, policy: Record):
        self.backend, self.context, self.policy = backend, context, policy
        self.request_id = context["request_id"]
        self.intake_receipt = ""
        self.intake_ticket_id = ""
        self.verified_ticket_id = ""
        self.recovery_queue = "operations"

    async def handoff(self, queue: str, reason: str, ticket_id: str = "") -> Outcome:
        ticket_id = ticket_id or self.intake_ticket_id or self.verified_ticket_id
        args = {"queue": queue, "reason": reason}
        if ticket_id:
            args["ticket_id"] = ticket_id
        prefix = (SAFETY_REPLY + " " if queue == "safety" else "") + self.intake_receipt
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
                "This assistant records service tickets, books visits and handles service credits. This request needs human review.",
            )
        if decision.intent == "credit":
            self.recovery_queue = "billing"
            return await self.credit_service(decision)
        if self.context["actor"].get("role") not in {"customer", "dispatcher", "supervisor"}:
            return Outcome(
                "blocked",
                "Your current role is not authorized to create tickets or schedule service.",
            )
        try:
            if decision.intent == "intake":
                return await self.intake_service(decision)
            time_question = self._time_question(decision)
            if not decision.ticket_id:
                return clarification("identity")
            if time_question:
                return time_question
            return await self.schedule_service(decision)
        except BackendError as exc:
            if exc.code in {"RECORD_UNAVAILABLE", "FORBIDDEN", "UNVERIFIED"}:
                return Outcome(
                    "blocked",
                    self.intake_receipt
                    + "The requested record is unavailable within your authorized account. Please confirm the reference or contact operations for access verification.",
                )
            return await self.handoff(
                "operations",
                "Service could not be completed because a tool was unavailable or live state changed. Operations must reconcile any uncertain ticket or booking before retrying.",
            )
        except (KeyError, ValueError, TypeError):
            return await self.handoff(
                "operations",
                "Current service records or policy need reconciliation before a booking can be confirmed.",
            )

    async def credit_service(self, decision: Decision) -> Outcome:
        if self.context["actor"].get("role") not in {
            "customer",
            "dispatcher",
            "finance",
            "supervisor",
        }:
            return Outcome(
                "blocked", "Your current role is not authorized to request or apply credits."
            )
        if decision.currency != "USD":
            return Outcome(
                "blocked",
                "Service credits support USD only. No currency conversion or credit was performed.",
            )
        if not decision.invoice_id and not decision.ticket_id and not decision.asset_id:
            return clarification("invoice")
        try:
            return await self._credit(decision)
        except BackendError as exc:
            if exc.code in {"RECORD_UNAVAILABLE", "FORBIDDEN", "UNVERIFIED"}:
                return Outcome(
                    "blocked",
                    "The requested billing record is unavailable within your authorized account. Please confirm the reference or contact support for access verification.",
                )
            return await self.handoff(
                "billing",
                "The credit or approval could not be confirmed because a tool was unavailable or current records changed. Billing must reconcile any uncertain action before retrying.",
            )
        except (KeyError, ValueError, TypeError):
            return await self.handoff(
                "billing",
                "Current billing records or policy need reconciliation before a credit can be confirmed.",
            )

    async def _credit(self, decision: Decision) -> Outcome:
        b = self.backend
        invoice_id = decision.invoice_id
        ticket_id = decision.ticket_id
        if not invoice_id and not ticket_id:
            asset = await b.record("assets", decision.asset_id)
            if asset["customer_id"] not in self.context["actor"]["customer_ids"]:
                raise BackendError("FORBIDDEN")
            if decision.site_id and decision.site_id != asset["site_id"]:
                return clarification("invoice")
            tickets = [
                row
                for row in await b.search("tickets", asset["id"])
                if row["asset_id"] == asset["id"]
            ]
            if len(tickets) != 1:
                return clarification("invoice")
            ticket_id = tickets[0]["id"]
        if not invoice_id:
            # Validate an explicit ticket even if no invoice search result matches it.
            ticket = await b.record("tickets", ticket_id)
            if ticket["customer_id"] not in self.context["actor"]["customer_ids"]:
                raise BackendError("FORBIDDEN")
            self.verified_ticket_id = ticket["id"]
            invoices = [
                row
                for row in await b.search("invoices", ticket["id"])
                if row["ticket_id"] == ticket["id"]
            ]
            if len(invoices) != 1:
                return clarification("invoice")
            invoice_id = invoices[0]["id"]
        invoice = await b.record("invoices", invoice_id)
        ticket = await b.record("tickets", invoice["ticket_id"])
        if any(
            row["customer_id"] not in self.context["actor"]["customer_ids"]
            for row in [invoice, ticket]
        ):
            raise BackendError("FORBIDDEN")
        self.verified_ticket_id = ticket["id"]
        if invoice["customer_id"] != ticket["customer_id"]:
            raise ValueError("Conflicting invoice and ticket ownership")
        if (
            (decision.ticket_id and decision.ticket_id != ticket["id"])
            or (decision.site_id and decision.site_id != ticket["site_id"])
            or (decision.asset_id and decision.asset_id != ticket["asset_id"])
        ):
            return clarification("invoice")
        if decision.amount_cents is None or decision.amount_cents <= 0:
            return clarification("amount")
        self.policy = await b.call("get_policy")
        rules = self.policy["rules"]
        b.remember("policy", rules["version"])
        credit_policy = rules["credit"]
        limit = credit_policy["auto_limit_cents"]
        always = credit_policy["always_requires_approval"]
        total, credited = invoice["total_cents"], invoice["credited_cents"]
        if (
            rules["currency"] != "USD"
            or invoice["currency"] != "USD"
            or type(limit) is not int
            or limit < 0
            or type(always) is not bool
            or type(total) is not int
            or type(credited) is not int
            or not 0 <= credited <= total
            or type(ticket["sla_breached"]) is not bool
        ):
            raise ValueError("Invalid billing policy or ledger")
        if invoice["status"] != "paid":
            return Outcome(
                "blocked",
                f"Invoice {invoice_id} is not recorded as paid. A service credit requires a paid invoice. No credit or approval request was created.",
            )
        if not ticket["sla_breached"]:
            return Outcome(
                "blocked",
                f"Ticket {ticket['id']} has no authoritative SLA breach recorded. No credit or approval request was created for invoice {invoice_id}.",
            )
        amount = decision.amount_cents
        assert amount is not None
        remaining = total - credited
        if amount > remaining:
            if remaining == 0:
                return Outcome(
                    "blocked",
                    f"Invoice {invoice_id} has no remaining paid amount available for credit. No credit or approval request was created.",
                )
            return Outcome(
                "needs_clarification",
                f"Only {dollars(remaining)} remains available for credit on invoice {invoice_id}. Would you like to request that amount instead? No credit or approval request was created.",
            )
        args: Record = {
            "invoice_id": invoice_id,
            "amount_cents": amount,
            "reason": f"Service credit for the authoritative SLA breach on ticket {ticket['id']}.",
        }
        if always or amount > limit:
            approvals = [
                row
                for row in await b.search("approvals", invoice_id)
                if row.get("invoice_id") == invoice_id
                and type(row.get("amount_cents")) is int
                and row["amount_cents"] == amount
                and row.get("customer_id") == invoice["customer_id"]
            ]
            grant = None
            pending = None
            for candidate in sorted(approvals, key=lambda row: row["id"]):
                # Search is for discovery; read the current grant before using it.
                row = await b.record("approvals", candidate["id"])
                if (
                    row.get("invoice_id") != invoice_id
                    or type(row.get("amount_cents")) is not int
                    or row["amount_cents"] != amount
                    or row.get("customer_id") != invoice["customer_id"]
                ):
                    continue
                if row.get("status") == "pending":
                    pending = row
                elif (
                    row.get("status") == "granted"
                    and row.get("issuer_role") == "supervisor"
                    and utc(row["expires_at"]) > utc(self.context["now"])
                ):
                    grant = row
                    break
            if grant:
                args["approval_id"] = grant["id"]
            else:
                if pending is None:
                    pending = await b.call(
                        "request_approval",
                        **args,
                        idempotency_key=operation_key(self.request_id, "request_approval", args),
                    )
                if (
                    pending.get("status") != "pending"
                    or pending.get("invoice_id") != invoice_id
                    or pending.get("amount_cents") != amount
                ):
                    raise ValueError("Unconfirmed approval request")
                b.remember("approvals", pending["id"])
                return Outcome(
                    "escalated",
                    f"Supervisor approval {pending['id']} is pending for a {dollars(amount)} credit on invoice {invoice_id}. No credit has been applied.",
                )
        credit = await b.call(
            "issue_credit",
            **args,
            idempotency_key=operation_key(self.request_id, "issue_credit", args),
        )
        if credit.get("invoice_id") != invoice_id or credit.get("amount_cents") != amount:
            raise ValueError("Unconfirmed credit")
        b.remember("credits", credit["id"])
        return Outcome(
            "completed",
            f"Applied a {dollars(amount)} service credit to invoice {invoice_id}. Credit reference: {credit['id']}.",
        )

    @staticmethod
    def _time_question(decision: Decision) -> Outcome | None:
        if decision.time_mode == "unclear":
            return clarification("time")
        if decision.time_mode == "exact":
            try:
                utc(decision.starts_at)
            except (ValueError, TypeError):
                return clarification("time")
        return None

    async def _eligible(
        self, decision: Decision
    ) -> tuple[Record, Record, Record, list[Record]] | Outcome:
        ticket = await self.backend.record("tickets", decision.ticket_id)
        if ticket["customer_id"] in self.context["actor"]["customer_ids"]:
            self.verified_ticket_id = ticket["id"]
        records = await self._service_records(decision, ticket)
        if isinstance(records, Outcome):
            return records
        asset, site, contracts = records
        rules = self.policy["rules"]["scheduling"]
        if rules.get("duration_minutes") != 60 or any(
            rules.get(k) is not True
            for k in ["require_skill", "require_region", "require_safety_clearance"]
        ):
            return await self.handoff(
                "operations", "The current scheduling policy needs human review.", ticket["id"]
            )
        return ticket, asset, site, contracts

    async def _service_records(
        self, decision: Decision, ticket: Record | None = None
    ) -> tuple[Record, Record, list[Record]] | Outcome:
        b = self.backend
        asset = await b.record("assets", ticket["asset_id"] if ticket else decision.asset_id)
        site = await b.record("sites", ticket["site_id"] if ticket else asset["site_id"])
        related = [asset, site] + ([ticket] if ticket else [])
        ticket_id = ticket["id"] if ticket else ""
        customer_ids = self.context["actor"]["customer_ids"]
        if any(row["customer_id"] not in customer_ids for row in related):
            return Outcome("blocked", "The requested records are outside your authorized account.")
        if len({row["customer_id"] for row in related}) != 1 or asset["site_id"] != site["id"]:
            return await self.handoff(
                "operations", "Current ticket, asset and site identity records conflict."
            )
        if (decision.site_id and decision.site_id != site["id"]) or (
            decision.asset_id and decision.asset_id != asset["id"]
        ):
            return clarification("identity")
        if asset.get("safety_hold") or (ticket and ticket.get("severity") == "S1"):
            return await self.handoff(
                "safety", "The asset or ticket requires safety clearance.", ticket_id
            )
        if asset["status"] != "active" or site["status"] != "active":
            return await self.handoff(
                "operations",
                "The asset or site is inactive and requires reconciliation.",
                ticket_id,
            )
        if ticket and ticket["status"] not in {"open", "in_progress"}:
            return Outcome(
                "blocked",
                "This ticket is resolved or unavailable for scheduling. No visit was booked.",
            )
        customer = await b.record("customers", site["customer_id"])
        if customer["account_status"] != "active":
            return await self.handoff(
                "operations",
                "The account needs review before service can be scheduled.",
                ticket_id,
            )
        self.policy = await b.call("get_policy")
        b.remember("policy", self.policy["rules"]["version"])
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
                ticket_id,
            )
        return asset, site, contracts

    async def _open_ticket(self, asset_id: str) -> Record | None:
        rows = [
            row
            for row in await self.backend.search("tickets", asset_id)
            if row["asset_id"] == asset_id and row["status"] in {"open", "in_progress"}
        ]
        if len(rows) > 1:
            raise BackendError("CONFLICTING_OPEN_TICKETS")
        return rows[0] if rows else None

    async def intake_service(self, decision: Decision) -> Outcome:
        if not decision.asset_id:
            return clarification("identity")
        if decision.issue_category == "unclear" or not decision.issue_summary.strip():
            return clarification("issue")
        ticket: Record | None
        # Explicit ticket references must never turn into permission to create a replacement.
        if decision.ticket_id:
            ticket = await self.backend.record("tickets", decision.ticket_id)
        else:
            ticket = await self._open_ticket(decision.asset_id)
        records = await self._service_records(decision, ticket)
        if isinstance(records, Outcome):
            return records
        asset, site, _ = records
        created = False
        if ticket is None:
            args = {
                "site_id": site["id"],
                "asset_id": asset["id"],
                "severity": "S2" if decision.issue_category == "interruption" else "S3",
                "summary": decision.issue_summary.strip(),
            }
            try:
                ticket = await self.backend.call(
                    "create_ticket",
                    **args,
                    idempotency_key=operation_key(self.request_id, "create_ticket", args),
                )
                created = True
            except BackendError as exc:
                if exc.code != "DUPLICATE_OPEN_TICKET":
                    raise
                # Reconcile one competing creation through scoped records, not error prose.
                ticket = await self._open_ticket(asset["id"])
                if ticket is None:
                    raise BackendError("DUPLICATE_UNRESOLVED") from None
                records = await self._service_records(decision, ticket)
                if isinstance(records, Outcome):
                    return records
        self.backend.remember("tickets", ticket["id"])
        self.intake_ticket_id = ticket["id"]
        self.intake_receipt = (
            f"{'Created' if created else 'Reused'} ticket {ticket['id']} "
            f"for asset {asset['id']} at site {site['id']}. "
        )
        if decision.intake_mode == "record_only":
            return Outcome("completed", self.intake_receipt + "No new visit was booked.")
        question = self._time_question(decision)
        if question:
            return Outcome(
                question.status, self.intake_receipt + "No new visit was booked. " + question.reply
            )
        booking = decision.model_copy(update={"intent": "schedule", "ticket_id": ticket["id"]})
        outcome = await self.schedule_service(booking)
        # Handoffs already include the receipt, including timeout recovery in orchestration.
        if self.intake_receipt in outcome.reply:
            return outcome
        return Outcome(outcome.status, self.intake_receipt + outcome.reply)

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
