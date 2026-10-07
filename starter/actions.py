"""Business actions return confirmed outcomes; the model supplies candidates only."""

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from .backend import Backend, BackendError, Record

SAFETY_REPLY = "Move away from the hazard and contact site emergency personnel. Routine service requires safety clearance."
# Used when no model safety screen completed, so a hazard cannot be ruled out.
SAFETY_FALLBACK = (
    "If anyone is in danger, move away from the hazard and contact site emergency personnel."
)


class RequestedTime(BaseModel):
    """Calendar fields the model read from the request; Python resolves the instant."""

    model_config = ConfigDict(extra="forbid")
    relative_day: Literal["none", "today", "tomorrow"]
    year: int | None = Field(strict=True)
    month: int | None = Field(strict=True)
    day: int | None = Field(strict=True)
    hour: int = Field(strict=True)
    minute: int = Field(strict=True)
    utc_offset_minutes: int | None = Field(strict=True)


class TimePreference(BaseModel):
    """A non-exact time preference the model read; Python lists matching open slots."""

    model_config = ConfigDict(extra="forbid")
    relative: Literal["none", "today", "tomorrow", "this_week", "next_week"]
    weekday: Literal[
        "none", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ]
    year: int | None = Field(strict=True)
    month: int | None = Field(strict=True)
    day: int | None = Field(strict=True)
    part_of_day: Literal["any", "morning", "afternoon", "evening"]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal[
        "schedule", "intake", "credit", "compose", "status", "clarify", "hazard", "unsupported"
    ]
    ticket_id: str = Field(default="", max_length=100)
    site_id: str = Field(default="", max_length=100)
    asset_id: str = Field(default="", max_length=100)
    time_mode: Literal["earliest", "exact", "unclear"] = "unclear"
    requested_time: RequestedTime | None = None
    time_preference: TimePreference | None = None
    # Resolved by Python from requested_time; never part of the model's output schema.
    starts_at: SkipJsonSchema[str] = Field(default="", max_length=80)
    clarification: Literal[
        "identity",
        "time",
        "intent",
        "issue",
        "conditional",
        "invoice",
        "amount",
        "mixed",
        "message",
        "recipient",
        "one_asset",
        "help",
    ] = "identity"
    status_topic: Literal["none", "ticket", "visit", "credit"] = "none"
    unsupported_kind: Literal[
        "reschedule_or_cancel",
        "message_delivery",
        "billing_inquiry",
        "repair_instructions",
        "ticket_change",
        "other",
    ] = "other"
    intake_mode: Literal["record_only", "record_and_schedule"] = "record_only"
    issue_category: Literal["interruption", "maintenance", "unclear"] = "unclear"
    issue_summary: str = Field(default="", max_length=500)
    invoice_id: str = Field(default="", max_length=100)
    amount_cents: int | None = Field(default=None, strict=True)
    amount_percent: int | None = Field(default=None, strict=True)
    currency: Literal["USD", "unsupported"] = "USD"
    message_purpose: Literal["none", "appointment_update", "ticket_update"] = "none"
    recipient_mode: Literal["generic", "named"] = "generic"
    contact_id: str = Field(default="", max_length=100)


@dataclass(frozen=True)
class Message:
    subject: str
    body: str
    contact_id: str = ""

    def text(self) -> str:
        return f"Subject: {self.subject}\n\n{self.body}"


@dataclass(frozen=True)
class Outcome:
    status: str
    reply: str
    # A prepared message is always the final block of reply.
    message: Message | None = None


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


WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def site_zone(site: Record) -> tzinfo:
    """The site's recorded timezone; times without a stated zone are local to the site."""
    try:
        return ZoneInfo(site["timezone"])
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Site timezone unavailable") from exc


def display_zone(site: Record) -> tzinfo:
    """For showing a stored instant only: every displayed time also states UTC."""
    try:
        return site_zone(site)
    except ValueError:
        return timezone.utc


def display_time(value: str, zone: tzinfo = timezone.utc) -> str:
    """A date and clock time in the site's zone, always with the UTC time."""
    instant = utc(value)
    local = instant.astimezone(zone)
    text = f"{local.day} {local:%B %Y}, {local.hour % 12 or 12}:{local:%M} {local:%p}"
    if local.utcoffset() == timedelta(0):
        return text + " UTC"
    return f"{text} {local.tzname()} ({instant:%H:%M} UTC)"


def resolve_requested_time(requested: RequestedTime, now: str, zone: tzinfo = timezone.utc) -> str:
    """Resolve model-read calendar fields using only the request-scoped clock.

    The model decides what the user meant; this only does calendar arithmetic.
    A time without a stated offset is local to the site's zone. An omitted year
    means the current calendar year in that zone, even when that date has passed.
    Availability checks decide whether it is bookable.
    """
    if requested.utc_offset_minutes is not None:
        if not -720 <= requested.utc_offset_minutes <= 840:
            raise ValueError("Invalid UTC offset")
        zone = timezone(timedelta(minutes=requested.utc_offset_minutes))
    scoped_now = utc(now).astimezone(zone)
    if requested.relative_day != "none":
        if any(v is not None for v in [requested.year, requested.month, requested.day]):
            raise ValueError("Relative day conflicts with a calendar date")
        day = scoped_now.date() + timedelta(days=int(requested.relative_day == "tomorrow"))
    else:
        if requested.month is None or requested.day is None:
            raise ValueError("One calendar date required")
        day = datetime(requested.year or scoped_now.year, requested.month, requested.day).date()
    local = datetime.combine(day, datetime.min.time()).replace(
        hour=requested.hour, minute=requested.minute
    )
    instant = local.replace(tzinfo=zone)
    # A wall time skipped or repeated by a daylight-saving change is not one instant.
    if instant.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != local or (
        instant.utcoffset() != instant.replace(fold=1).utcoffset()
    ):
        raise ValueError("Ambiguous local time")
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_time(decision: Decision, now: str, zone: tzinfo = timezone.utc) -> Decision:
    """Fill starts_at from requested_time, or mark the time unclear so the user is asked."""
    if decision.requested_time is None:
        return decision
    try:
        if decision.time_mode != "exact":
            raise ValueError("Conflicting time modes")
        resolved = resolve_requested_time(decision.requested_time, now, zone)
        return decision.model_copy(update={"starts_at": resolved})
    except (ValueError, TypeError, OverflowError):
        return decision.model_copy(update={"time_mode": "unclear", "starts_at": ""})


def name(value: object) -> str:
    """A record name made safe for a reply: plain text on one line, no Markdown syntax."""
    text = " ".join(str(value or "").split())
    text = "".join(ch for ch in text if ch.isalnum() or ch in " .,-'&/")
    return text[:60].strip()


def describe(asset: Record, site: Record) -> str:
    """Equipment and site names beside their IDs, for the assistant's own replies."""
    label = name(asset.get("label")) or "equipment"
    place = name(site.get("name")) or "site"
    return f"{label} ({asset['id']}) at {place} ({site['id']})"


def article(word: str) -> str:
    return "An" if word[:1].lower() in "aeiou" else "A"


HELP_REPLY = (
    "I can help with:\n"
    "- booking a technician visit for an open ticket\n"
    "- recording a new service issue for your equipment\n"
    "- checking a ticket's status or its next visit\n"
    "- checking or requesting a service credit on a paid invoice\n"
    "- writing a ticket-status or appointment update you can copy\n\n"
    "What would you like to do? Mention the ticket, equipment or invoice if you know it."
)

UNSUPPORTED = {
    "reschedule_or_cancel": "I can't reschedule or cancel existing visits yet.",
    "message_delivery": "I can write a message for you to copy, but I can't send emails, save drafts or retrieve old drafts.",
    "billing_inquiry": "I can't answer general invoice or approval-status questions yet.",
    "repair_instructions": "I can't give repair instructions or promise repair outcomes or compensation.",
    "ticket_change": "I can't change an existing ticket's severity or status.",
    "other": "That request is outside what I can do here.",
}


def clarification(reason: str, decision: Decision | None = None) -> Outcome:
    ticket = decision.ticket_id if decision else ""
    questions = {
        "invoice": "Which invoice or service ticket is the credit for?",
        "amount": "What exact amount in USD would you like credited? Please use a positive amount in whole cents.",
        "mixed": "I handle credits and service requests one at a time. Which would you like me to do first? No action has been taken.",
        "identity": "Which ticket, or which equipment and site, do you mean?",
        "issue": "What is wrong with the equipment: has it stopped working, or does it need nonurgent maintenance?",
        "conditional": "Recording a ticket, booking a visit and preparing a message are separate steps. May I keep the completed steps if a later step cannot finish?",
        "time": "When would you like the visit? Tell me a date and time, or ask for the earliest available slot. Times are in the site's local timezone unless you state another.",
        "intent": HELP_REPLY,
        "help": HELP_REPLY,
        "message": (
            f"Would you like a message about the current status of ticket {ticket}, or about its confirmed appointment?"
            if ticket
            else "Would you like a message about a ticket's current status or a confirmed appointment? Which ticket is it for?"
        ),
        "recipient": "Who should the message be for? Name a registered contact authorized for this site, or ask for a message without a named recipient.",
        "one_asset": "I can handle one piece of equipment per request. Which one should I start with? No action has been taken.",
    }
    return Outcome("needs_clarification", questions[reason])


class Actions:
    def __init__(
        self,
        backend: Backend,
        context: Record,
        policy: Record,
        verify: Callable[[str, Record], Awaitable[bool]] | None = None,
    ):
        self.backend, self.context, self.policy = backend, context, policy
        # An independent check, asked once before a request's first business write.
        self.verify = verify
        self.write_confirmed = False
        self.request_id = context["request_id"]
        self.intake_receipt = ""
        self.intake_ticket_id = ""
        self.verified_ticket_id = ""
        self.confirmed_reply = ""
        self.recovery_queue = "operations"
        self.safety_handoff: tuple[str, str] | None = None
        self.contact_name = ""

    async def _confirm_write(self, action: str) -> Outcome | None:
        """Before the first business write, confirm the user asked for exactly this change.

        Handoffs and supervisor-approval requests are not gated: they only route work
        to a person. A rejected check writes nothing and asks the user, so their reply
        can confirm the change. The checker also sees the account's equipment, so it
        can judge whether the user's description picks out the proposed record.
        """
        if self.verify is None or self.write_confirmed:
            return None
        customers = self.context["actor"]["customer_ids"]
        sites = {s["id"]: s for s in await self.backend.search("sites")}
        equipment = [
            describe(a, sites[a["site_id"]])
            for a in sorted(await self.backend.search("assets"), key=lambda a: a["id"])
            if a.get("customer_id") in customers and a.get("site_id") in sites
        ][:40]
        facts = {
            "current_time": display_time(self.context["now"]),
            "site_timezones": {
                s["id"]: s.get("timezone")
                for s in sites.values()
                if s.get("customer_id") in customers
            },
            "account_equipment": equipment,
        }
        if await self.verify(action, facts):
            self.write_confirmed = True
            return None
        return Outcome(
            "needs_clarification",
            f"Before I make any change, please confirm: should I {action}? Nothing has been changed.",
        )

    async def handoff(self, queue: str, reason: str, ticket_id: str = "") -> Outcome:
        ticket_id = ticket_id or self.intake_ticket_id or self.verified_ticket_id
        # Latch before the first await. Recovery must replay this exact safety operation,
        # including a response lost after commit, rather than create an operations handoff.
        if queue == "safety" and self.safety_handoff is None:
            self.safety_handoff = (reason, ticket_id)
            self.recovery_queue = "safety"
        if self.safety_handoff is not None:
            queue = "safety"
            reason, ticket_id = self.safety_handoff
        args = {"queue": queue, "reason": reason}
        if ticket_id:
            args["ticket_id"] = ticket_id
        prefix = (SAFETY_REPLY + " " if queue == "safety" else "") + (
            self.confirmed_reply + " " if self.confirmed_reply else self.intake_receipt
        )
        try:
            row = await self.backend.call(
                "escalate",
                recovery=True,
                **args,
                idempotency_key=operation_key(self.request_id, "escalate", args),
            )
            self.backend.remember("escalations", row["id"])
            return Outcome(
                "escalated",
                prefix + f"{reason} {article(queue)} {queue} handoff is recorded as {row['id']}.",
            )
        except BackendError:
            return Outcome(
                "error",
                prefix
                + "The remaining work could not be confirmed, and the human handoff could not be confirmed. Please contact operations directly.",
            )

    async def handle(self, decision: Decision) -> Outcome:
        if decision.intent == "hazard" or self.safety_handoff is not None:
            return await self.handoff(
                "safety", "A possible emergency requires immediate human safety review."
            )
        if not self.context["actor"].get("verified"):
            return await self.handoff(
                "identity", "Requester identity must be verified before accessing service records."
            )
        if decision.intent == "unsupported":
            return await self.handoff(
                "operations",
                UNSUPPORTED[decision.unsupported_kind]
                + " I've passed your request to the operations team for review.",
            )
        if decision.intent == "credit" or (
            decision.intent == "status" and decision.status_topic == "credit"
        ):
            if decision.message_purpose != "none":
                return clarification("mixed")
            self.recovery_queue = "billing"
            return await self.credit_service(decision)
        roles = {"customer", "dispatcher", "supervisor"}
        if decision.intent in {"compose", "status", "clarify"}:
            roles.add("finance")
        if decision.intent in {"status", "clarify"}:
            roles.add("viewer")
        if self.context["actor"].get("role") not in roles:
            return Outcome(
                "blocked",
                "Your current role is not authorized for this requested workflow.",
            )
        try:
            if decision.intent == "clarify":
                if decision.clarification == "identity":
                    return await self._identity_options()
                return clarification(decision.clarification, decision)
            if decision.intent == "status":
                return await self.answer_status(decision)
            if decision.intent == "compose" and decision.message_purpose == "none":
                return clarification("message", decision)
            if decision.message_purpose != "none":
                if decision.recipient_mode == "named" and not decision.contact_id:
                    return clarification("recipient")
                if (
                    decision.intent == "intake"
                    and decision.intake_mode == "record_only"
                    and decision.message_purpose == "appointment_update"
                ):
                    return clarification("message", decision)
            if decision.intent == "compose":
                return await self.compose_message(decision)
            if decision.intent == "intake":
                outcome = await self.intake_service(decision)
            else:
                if not decision.ticket_id:
                    return await self._ticket_options(
                        "Which ticket should I book a visit for?",
                        ask_time=decision.time_mode == "unclear",
                    )
                outcome = await self.schedule_service(decision)
            if outcome.status != "completed" or decision.message_purpose == "none":
                return outcome
            self.confirmed_reply = outcome.reply
            message = await self.compose_message(
                decision.model_copy(update={"ticket_id": self.verified_ticket_id})
            )
            if self.confirmed_reply in message.reply:
                return message
            return Outcome(
                message.status, self.confirmed_reply + "\n\n" + message.reply, message.message
            )
        except BackendError as exc:
            if exc.code in {"RECORD_UNAVAILABLE", "FORBIDDEN", "UNVERIFIED"}:
                return Outcome(
                    "blocked",
                    (self.confirmed_reply + " " if self.confirmed_reply else self.intake_receipt)
                    + "The requested record is unavailable within your authorized account. Please confirm the reference or contact operations for access verification.",
                )
            return await self.handoff(
                "operations",
                "The remaining request could not be completed because a tool was unavailable or live state changed. Operations must reconcile any uncertain action before retrying.",
            )
        except (KeyError, ValueError, TypeError):
            return await self.handoff(
                "operations",
                "Current service records or policy need reconciliation before the remaining request can be completed.",
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
        remaining = total - credited
        ineligible = ""
        if invoice["status"] != "paid":
            ineligible = f"Invoice {invoice_id} is not recorded as paid. A service credit requires a paid invoice."
        elif not ticket["sla_breached"]:
            ineligible = f"Ticket {ticket['id']} has no authoritative SLA breach recorded, so invoice {invoice_id} is not eligible for a service credit."
        elif remaining == 0:
            ineligible = f"Invoice {invoice_id} has no remaining paid amount available for credit."
        if decision.intent == "status":
            # A read-only eligibility answer; it never requests or applies a credit.
            if ineligible:
                return Outcome("completed", ineligible)
            return Outcome(
                "completed",
                f"Invoice {invoice_id} for ticket {ticket['id']} is eligible for a service credit of up to {dollars(remaining)}{self._approval_note(limit, always, remaining)}. If you'd like a credit on it, tell me the amount.",
            )
        if ineligible:
            return Outcome("blocked", ineligible + " No credit or approval request was created.")
        amount = decision.amount_cents
        if amount is None and decision.amount_percent is not None:
            return self._percent_question(
                decision.amount_percent, invoice_id, total, remaining, limit, always
            )
        if amount is None or amount <= 0:
            return Outcome(
                "needs_clarification",
                f"Invoice {invoice_id} for ticket {ticket['id']} can receive up to {dollars(remaining)} in service credit{self._approval_note(limit, always, remaining)}. What exact amount in USD would you like credited? No credit or approval request was created.",
            )
        if amount > remaining:
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
            b.cite("approvals", approvals)
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
                    # Not gated: a pending approval only asks a supervisor to review;
                    # the credit itself is checked before issue_credit.
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
        check = await self._confirm_write(
            f"apply a {dollars(amount)} service credit to {await self._invoice_label(invoice, ticket)}"
        )
        if check:
            return check
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

    async def _invoice_label(self, invoice: Record, ticket: Record) -> str:
        """Invoice, ticket and equipment names for the write check; only read when checking."""
        label = f"invoice {invoice['id']}"
        if self.verify is None or self.write_confirmed:
            return label
        asset = await self.backend.record("assets", ticket["asset_id"])
        site = await self.backend.record("sites", ticket["site_id"])
        return f"{label} (the invoice for ticket {ticket['id']} on {describe(asset, site)})"

    @staticmethod
    def _approval_note(limit: int, always: bool, remaining: int) -> str:
        if always:
            return "; any credit needs supervisor approval"
        if limit < remaining:
            return f"; credits above {dollars(limit)} need supervisor approval"
        return ""

    @staticmethod
    def _percent_question(
        percent: int, invoice_id: str, total: int, remaining: int, limit: int, always: bool
    ) -> Outcome:
        """Convert a requested percentage to exact cents for confirmation; never apply it."""
        if not 0 < percent <= 100:
            return clarification("amount")
        if total * percent % 100:
            return Outcome(
                "needs_clarification",
                f"{percent}% of invoice {invoice_id}'s {dollars(total)} total is not a whole-cent amount. What exact amount in USD would you like credited? No credit or approval request was created.",
            )
        amount = total * percent // 100
        if amount > remaining:
            return Outcome(
                "needs_clarification",
                f"{percent}% of invoice {invoice_id}'s {dollars(total)} total is {dollars(amount)}, but only {dollars(remaining)} remains available for credit. What amount would you like instead? No credit or approval request was created.",
            )
        # Name the step that would actually follow, so a "yes" confirms that exact step.
        step = (
            f"request supervisor approval for a {dollars(amount)} service credit"
            if always or amount > limit
            else f"apply a {dollars(amount)} service credit"
        )
        return Outcome(
            "needs_clarification",
            f"{percent}% of invoice {invoice_id}'s {dollars(total)} total is {dollars(amount)}. Would you like me to {step} to invoice {invoice_id}? No credit or approval request was created.",
        )

    async def _ticket_lines(self) -> list[str]:
        """The requester's own open tickets, with equipment and site names, as options."""
        b = self.backend
        customers = self.context["actor"]["customer_ids"]
        tickets = sorted(
            (
                t
                for t in await b.search("tickets")
                if t.get("customer_id") in customers and t.get("status") in {"open", "in_progress"}
            ),
            key=lambda t: t["id"],
        )
        if not tickets:
            return []
        assets = {a["id"]: a for a in await b.search("assets")}
        sites = {s["id"]: s for s in await b.search("sites")}
        lines = []
        for t in b.cite("tickets", tickets[:3]):
            asset, site = assets.get(t["asset_id"]), sites.get(t["site_id"])
            where = (
                describe(asset, site)
                if asset and site
                else f"equipment {t['asset_id']} at site {t['site_id']}"
            )
            lines.append(f"- {t['id']}: {where}, {t['status'].replace('_', ' ')}")
        return lines

    async def _equipment_lines(self) -> list[str]:
        """The requester's own active equipment, with site names, as options."""
        customers = self.context["actor"]["customer_ids"]
        assets = sorted(
            (
                a
                for a in await self.backend.search("assets")
                if a.get("customer_id") in customers and a.get("status") == "active"
            ),
            key=lambda a: a["id"],
        )
        if not assets:
            return []
        sites = {s["id"]: s for s in await self.backend.search("sites")}
        shown = self.backend.cite("assets", [a for a in assets[:3] if a["site_id"] in sites])
        return [f"- {describe(a, sites[a['site_id']])}" for a in shown]

    async def _ticket_options(self, question: str, ask_time: bool = False) -> Outcome:
        """Ask which ticket, offering the requester's own open tickets as verified options."""
        lines = await self._ticket_lines()
        if lines:
            text = (
                f"{question} Your open tickets:\n"
                + "\n".join(lines)
                + "\n\nReply with the ticket, or describe the equipment if it isn't listed."
            )
        else:
            text = f"{question} You have no open tickets. To record a new issue, tell me the equipment, its site and what is wrong."
        if ask_time:
            text += " Also tell me when: the earliest available slot, or a date and time."
        return Outcome("needs_clarification", text)

    async def _equipment_options(self, question: str, ask_time: bool = False) -> Outcome:
        """Ask which equipment, offering the requester's own active assets as verified options."""
        lines = await self._equipment_lines()
        if not lines:
            return clarification("identity")
        text = f"{question} Your equipment:\n" + "\n".join(lines) + "\n\nReply with the equipment."
        if ask_time:
            text += " Also tell me when: the earliest available slot, or a date and time."
        return Outcome("needs_clarification", text)

    async def _identity_options(self) -> Outcome:
        """Ask which record a description meant, offering open tickets and active equipment."""
        tickets, equipment = await self._ticket_lines(), await self._equipment_lines()
        if not tickets and not equipment:
            return clarification("identity")
        text = clarification("identity").reply
        if tickets:
            text += " Your open tickets:\n" + "\n".join(tickets)
        if equipment:
            text += ("\n\nYour equipment:\n" if tickets else " Your equipment:\n") + "\n".join(
                equipment
            )
        return Outcome("needs_clarification", text + "\n\nReply with the ticket or the equipment.")

    async def answer_status(self, decision: Decision) -> Outcome:
        """Answer a ticket or visit question from verified records; never writes."""
        if not decision.ticket_id:
            return await self._ticket_options("Which ticket would you like the status of?")
        b = self.backend
        ticket = await b.record("tickets", decision.ticket_id)
        asset = await b.record("assets", ticket["asset_id"])
        site = await b.record("sites", ticket["site_id"])
        if any(
            r["customer_id"] not in self.context["actor"]["customer_ids"]
            for r in [ticket, asset, site]
        ):
            return Outcome("blocked", "The requested records are outside your authorized account.")
        self.verified_ticket_id = ticket["id"]
        status = {"open": "open", "in_progress": "in progress", "resolved": "resolved"}.get(
            ticket["status"]
        )
        if status is None or (
            status == "resolved" and ticket.get("resolution_verified") is not True
        ):
            return await self.handoff(
                "operations", "The ticket status needs reconciliation before it can be reported."
            )
        lines = [
            f"Ticket {ticket['id']} for {describe(asset, site)} is {status} (severity {name(ticket.get('severity'))})."
        ]
        if asset.get("safety_hold") is True or ticket.get("severity") == "S1":
            lines.append("It is on safety hold, so routine visits need safety clearance first.")
        now = utc(self.context["now"])
        visits = sorted(
            (
                v
                for v in await b.search("visits", ticket["id"])
                if v.get("ticket_id") == ticket["id"]
                and v.get("status") == "scheduled"
                and utc(v["starts_at"]) > now
            ),
            key=lambda v: utc(v["starts_at"]),
        )
        if visits:
            visit = b.cite("visits", visits[:1])[0]
            lines.append(
                f"The next one-hour visit is booked for {display_time(visit['starts_at'], display_zone(site))} with technician {visit['technician_id']} (visit {visit['id']})."
            )
        elif status != "resolved":
            lines.append(
                "No upcoming visit is booked. Would you like me to book the earliest available slot?"
            )
        return Outcome("completed", " ".join(lines))

    async def _message_recipient(self, decision: Decision, site: Record) -> Outcome | None:
        if decision.recipient_mode == "generic" and not decision.contact_id:
            return None
        if not decision.contact_id:
            return clarification("recipient")
        contact = await self.backend.record("contacts", decision.contact_id)
        if (
            contact.get("authorized") is not True
            or contact["customer_id"] != site["customer_id"]
            or not isinstance(contact.get("site_ids"), list)
            or site["id"] not in contact["site_ids"]
        ):
            return Outcome(
                "blocked", "The requested contact is not authorized for this site's message."
            )
        self.contact_name = name(contact.get("name"))
        return None

    async def _record_safety(self, record: Record, ticket_id: str = "") -> Outcome | None:
        if record.get("customer_id") in self.context["actor"]["customer_ids"] and (
            record.get("safety_hold") or record.get("severity") == "S1"
        ):
            return await self.handoff(
                "safety", "The asset or ticket requires safety clearance.", ticket_id
            )
        return None

    async def compose_message(self, decision: Decision) -> Outcome:
        """Return a bounded message from current records; never store or send it."""
        if not decision.ticket_id:
            return await self._ticket_options("Which ticket is the message for?")
        b = self.backend
        ticket = await b.record("tickets", decision.ticket_id)
        self.verified_ticket_id = ticket["id"]
        safety = await self._record_safety(ticket, ticket["id"])
        if safety:
            return safety
        asset = await b.record("assets", ticket["asset_id"])
        safety = await self._record_safety(asset, ticket["id"])
        if safety:
            return safety
        site = await b.record("sites", ticket["site_id"])
        rows = [ticket, asset, site]
        if any(r["customer_id"] not in self.context["actor"]["customer_ids"] for r in rows):
            return Outcome("blocked", "The requested records are outside your authorized account.")
        if len({r["customer_id"] for r in rows}) != 1 or asset["site_id"] != site["id"]:
            return await self.handoff(
                "operations", "Current ticket, asset and site identity records conflict."
            )
        if (decision.site_id and decision.site_id != site["id"]) or (
            decision.asset_id and decision.asset_id != asset["id"]
        ):
            return clarification("identity")
        await b.record("customers", site["customer_id"])
        self.policy = await b.call("get_policy")
        b.remember("policy", self.policy["rules"]["version"])
        recipient_problem = await self._message_recipient(decision, site)
        if recipient_problem:
            return recipient_problem
        status = {"open": "open", "in_progress": "in progress", "resolved": "resolved"}.get(
            ticket["status"]
        )
        if status is None or (
            status == "resolved" and ticket.get("resolution_verified") is not True
        ):
            return await self.handoff(
                "operations",
                "The ticket status needs reconciliation before a message can be prepared.",
            )
        # Only identifiers and bounded state are copied. Notes, names, summaries,
        # requested prose and communications never become message instructions/content.
        subject = f"Service update for ticket {ticket['id']}"
        body = (
            f"Ticket {ticket['id']} for equipment {asset['id']} at site {site['id']} is {status}."
        )
        if decision.message_purpose == "appointment_update":
            visits = b.cite(
                "visits",
                [
                    v
                    for v in await b.search("visits", ticket["id"])
                    if v["ticket_id"] == ticket["id"]
                ],
            )
            if not visits:
                return Outcome(
                    "needs_clarification",
                    "There is no confirmed appointment for this ticket. Would you like a ticket-status message instead?",
                )
            if len(visits) != 1:
                return await self.handoff(
                    "operations",
                    "Conflicting visit records need reconciliation before an appointment message can be prepared.",
                )
            visit = visits[0]
            if (
                visit["customer_id"] != site["customer_id"]
                or visit.get("status") != "scheduled"
                or visit.get("duration_minutes") != 60
                or status == "resolved"
                or utc(visit["starts_at"]) <= utc(self.context["now"])
            ):
                return await self.handoff(
                    "operations",
                    "The current visit cannot support a confirmed upcoming appointment message.",
                )
            subject = f"Confirmed appointment for ticket {ticket['id']}"
            body = (
                f"A one-hour service visit for ticket {ticket['id']}, equipment {asset['id']} "
                f"at site {site['id']}, is confirmed for {display_time(visit['starts_at'], display_zone(site))}. "
                f"The visit reference is {visit['id']}. Repair completion is not yet confirmed."
            )
        elif decision.message_purpose != "ticket_update":
            return clarification("message")
        elif status != "resolved":
            body += " Repair completion is not yet confirmed."
        recipient = ""
        if decision.contact_id:
            who = (
                f"{self.contact_name} ({decision.contact_id})"
                if self.contact_name
                else decision.contact_id
            )
            recipient = f" For registered contact {who}."
        message = Message(subject, body, decision.contact_id)
        return Outcome(
            "completed",
            "Here is a message you can copy and send."
            + recipient
            + " It has not been sent or saved as a draft.\n\n"
            + message.text(),
            message,
        )

    @staticmethod
    def _exact(decision: Decision) -> bool:
        if decision.time_mode != "exact":
            return False
        try:
            utc(decision.starts_at)
            return True
        except (ValueError, TypeError):
            return False

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
        ticket_id = ticket["id"] if ticket else ""
        if ticket:
            safety = await self._record_safety(ticket, ticket_id)
            if safety:
                return safety
        asset = await b.record("assets", ticket["asset_id"] if ticket else decision.asset_id)
        safety = await self._record_safety(asset, ticket_id)
        if safety:
            return safety
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
        if ticket:
            self.verified_ticket_id = ticket["id"]
        if (decision.site_id and decision.site_id != site["id"]) or (
            decision.asset_id and decision.asset_id != asset["id"]
        ):
            return clarification("identity")
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
        if decision.message_purpose != "none":
            recipient_problem = await self._message_recipient(decision, site)
            if recipient_problem:
                return recipient_problem
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
        return asset, site, b.cite("contracts", contracts)

    async def _open_ticket(self, asset_id: str) -> Record | None:
        rows = [
            row
            for row in await self.backend.search("tickets", asset_id)
            if row["asset_id"] == asset_id and row["status"] in {"open", "in_progress"}
        ]
        if len(rows) > 1:
            raise BackendError("CONFLICTING_OPEN_TICKETS")
        return self.backend.cite("tickets", rows)[0] if rows else None

    async def intake_service(self, decision: Decision) -> Outcome:
        if not decision.asset_id:
            return await self._equipment_options(
                "Which equipment is this about?",
                ask_time=decision.intake_mode == "record_and_schedule"
                and decision.time_mode == "unclear",
            )
        ticket: Record | None
        # Explicit ticket references must never turn into permission to create a replacement.
        if decision.ticket_id:
            ticket = await self.backend.record("tickets", decision.ticket_id)
        else:
            ticket = await self._open_ticket(decision.asset_id)
        # The issue only matters when a new ticket must be created; an open one is reused.
        if ticket is None and (
            decision.issue_category == "unclear" or not decision.issue_summary.strip()
        ):
            return clarification("issue")
        records = await self._service_records(decision, ticket)
        if isinstance(records, Outcome):
            return records
        asset, site, _ = records
        created = False
        if ticket is None:
            plan = f"create a new {'service-interruption' if decision.issue_category == 'interruption' else 'maintenance'} ticket for {describe(asset, site)}"
            if decision.intake_mode == "record_and_schedule":
                plan += {
                    "earliest": " and book its earliest open technician visit",
                    "exact": " and book a technician visit at the time you requested",
                }.get(decision.time_mode, " and then offer you visit times")
            check = await self._confirm_write(plan)
            if check:
                return check
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
        self.verified_ticket_id = ticket["id"]
        self.intake_receipt = (
            f"{'Created' if created else 'Reused open'} ticket {ticket['id']} "
            f"for {describe(asset, site)}. "
        )
        if decision.intake_mode == "record_only":
            return Outcome("completed", self.intake_receipt + "No new visit was booked.")
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

    async def _valid_existing_visit(
        self, visit: Record, ticket: Record, asset: Record, site: Record, contracts: list[Record]
    ) -> bool:
        """A stored visit is evidence, but must still support the promised appointment."""
        try:
            if (
                visit.get("customer_id") != ticket["customer_id"]
                or visit.get("ticket_id") != ticket["id"]
                or visit.get("status") != "scheduled"
                or type(visit.get("duration_minutes")) is not int
                or visit["duration_minutes"] != 60
                or not isinstance(visit.get("starts_at"), str)
                or not isinstance(visit.get("technician_id"), str)
                or not visit["technician_id"]
            ):
                return False
            start = utc(visit["starts_at"])
            if (
                start <= utc(self.context["now"])
                or not self._within_access(site, visit["starts_at"])
                or not any(
                    c["starts_at"] <= start.date().isoformat() <= c["ends_at"] for c in contracts
                )
            ):
                return False
            tech = await self.backend.record("technicians", visit["technician_id"])
            # A booked slot is absent from list_slots because the visit occupies it.
            # The dispatch registry retains the technician's working slots.
            if not (
                tech["active"] is True
                and tech["region"] == site["region"]
                and asset["required_skill"] in tech["skills"]
                and any(utc(slot) == start for slot in tech["available_slots"])
            ):
                return False
            for other in await self.backend.search("visits", tech["id"]):
                if other["id"] == visit["id"] or other["technician_id"] != tech["id"]:
                    continue
                duration = other["duration_minutes"]
                if type(duration) is not int or duration <= 0:
                    return False
                other_start = utc(other["starts_at"])
                if start < other_start + timedelta(minutes=duration) and other_start < (
                    start + timedelta(hours=1)
                ):
                    return False
            return True
        except (BackendError, KeyError, ValueError, TypeError, AttributeError):
            return False

    async def schedule_service(self, decision: Decision) -> Outcome:
        b = self.backend
        # A conflict may justify one fresh investigation, never a blind write replay.
        for replan in range(2):
            eligible = await self._eligible(decision)
            if isinstance(eligible, Outcome):
                return eligible
            ticket, asset, site, contracts = eligible
            where = describe(asset, site)
            try:
                zone = site_zone(site)
            except ValueError:
                return await self.handoff(
                    "operations", "The site timezone needs reconciliation.", ticket["id"]
                )
            if decision.requested_time is not None:
                decision = resolve_time(decision, self.context["now"], zone)
            existing = b.cite(
                "visits",
                [
                    v
                    for v in await b.search("visits", ticket["id"])
                    if v["ticket_id"] == ticket["id"]
                ],
            )
            if existing:
                visit = existing[0]
                if len(existing) != 1 or not await self._valid_existing_visit(
                    visit, ticket, asset, site, contracts
                ):
                    return await self.handoff(
                        "operations", "Existing visit records need reconciliation.", ticket["id"]
                    )
                if self._exact(decision) and utc(visit["starts_at"]) != utc(decision.starts_at):
                    return Outcome(
                        "needs_clarification",
                        f"Ticket {ticket['id']} already has a visit at {display_time(visit['starts_at'], zone)}. Please confirm whether you want operations to reschedule it.",
                    )
                return self._booked(ticket["id"], where, visit, zone, existing=True)
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
            # Distinct open start times, earliest first; options never book anything.
            times = list(dict.fromkeys(utc(s["starts_at"]) for s in candidates))
            if decision.time_mode != "earliest" and not self._exact(decision) and times:
                return self._slot_options(
                    ticket["id"], where, times, decision.time_preference, zone
                )
            if self._exact(decision):
                wanted = utc(decision.starts_at)
                matching = [s for s in candidates if utc(s["starts_at"]) == wanted]
                if not matching and times:
                    nearest = sorted(sorted(times, key=lambda t: abs(t - wanted))[:3])
                    return Outcome(
                        "needs_clarification",
                        f"{display_time(decision.starts_at, zone)} is not available for ticket {ticket['id']}. The nearest open one-hour slots for {where} are:\n"
                        + "\n".join(f"- {display_time(t.isoformat(), zone)}" for t in nearest)
                        + "\n\nReply with the slot you want. No new visit was booked.",
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
            when = (
                "at the earliest open slot, " if decision.time_mode == "earliest" else ""
            ) + display_time(slot["starts_at"], zone)
            check = await self._confirm_write(
                f"book a one-hour technician visit for ticket {ticket['id']}, {where}, {when}"
            )
            if check:
                return (
                    Outcome(check.status, self.intake_receipt + check.reply)
                    if self.intake_receipt
                    else check
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
                return self._booked(ticket["id"], where, visit, zone)
            except BackendError as exc:
                if replan == 0 and exc.code in {
                    "SLOT_UNAVAILABLE",
                    "VERSION_CONFLICT",
                    "ALREADY_SCHEDULED",
                }:
                    continue
                raise
        raise BackendError("CONFLICT_UNRESOLVED")

    def _slot_options(
        self,
        ticket_id: str,
        where: str,
        times: list[datetime],
        preference: TimePreference | None,
        zone: tzinfo,
    ) -> Outcome:
        """Ask when, offering up to three verified open slots; never books."""
        matching = [t for t in times if self._matches(t, preference, zone)] if preference else times
        lead = f"When would you like the visit for ticket {ticket_id}, {where}?"
        if preference and not matching:
            lead += " There are no open slots matching that preference. The nearest open one-hour slots are:"
            matching = times
        elif preference:
            lead += " These open one-hour slots match your preference:"
        else:
            lead += " The next open one-hour slots are:"
        return Outcome(
            "needs_clarification",
            lead
            + "\n"
            + "\n".join(f"- {display_time(t.isoformat(), zone)}" for t in matching[:3])
            + "\n\nReply with the slot you want, or ask for the earliest. No visit has been booked.",
        )

    def _matches(self, start: datetime, preference: TimePreference, zone: tzinfo) -> bool:
        """Calendar filtering of a model-read preference, in the site's zone."""
        local = start.astimezone(zone)
        today = utc(self.context["now"]).astimezone(zone).date()
        monday = today - timedelta(days=today.weekday())
        if preference.relative == "next_week":
            monday += timedelta(days=7)
        days: set | None = None
        try:
            if preference.month and preference.day:
                days = {
                    datetime(preference.year or today.year, preference.month, preference.day).date()
                }
            elif preference.relative in {"today", "tomorrow"}:
                days = {today + timedelta(days=int(preference.relative == "tomorrow"))}
            elif preference.weekday != "none":
                index = list(WEEKDAYS).index(preference.weekday)
                if preference.relative in {"this_week", "next_week"}:
                    days = {monday + timedelta(days=index)}
                else:
                    days = {today + timedelta(days=(index - today.weekday()) % 7)}
            elif preference.relative in {"this_week", "next_week"}:
                days = {monday + timedelta(days=i) for i in range(7)}
        except ValueError:
            days = None
        hours = {"morning": (6, 12), "afternoon": (12, 17), "evening": (17, 22)}.get(
            preference.part_of_day, (0, 24)
        )
        return (days is None or local.date() in days) and hours[0] <= local.hour < hours[1]

    @staticmethod
    def _booked(
        ticket_id: str, where: str, visit: Record, zone: tzinfo, existing: bool = False
    ) -> Outcome:
        lead = "Already scheduled" if existing else "Booked"
        return Outcome(
            "completed",
            f"{lead}: ticket {ticket_id} for {where}, visit {visit['id']}, technician {visit['technician_id']}, at {display_time(visit['starts_at'], zone)} for one hour. Repair completion is not yet confirmed.",
        )
