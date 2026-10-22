"""
Deadline reminders — the delivery half of the deadline digest (app/core/deadlines.py).

Hourly (the worker loop, plus the hourly cron in .github/workflows/gmail-poll.yml that
wakes the free-tier server): every open application whose deadline is within 24 hours,
or within 3, gets one email per student listing everything closing soon. Each reminder
is sent once per deadline (Application.reminders_sent), and claimed before sending so
the loop and the cron firing together can't both send it.

Before this, reminders were only written to the internal calendar (CalendarEvent), which
nothing ever showed or sent.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from beanie import PydanticObjectId

from app.core.config import settings
from app.core.deadlines import REMINDERS, format_ist, is_open, reminder_due, reminder_key, time_left
from app.core.mailer import mail_configured, send_mail
from app.models.application import Application
from app.models.opportunity import Company, Opportunity
from app.models.user import Profile, User

logger = logging.getLogger(__name__)

WINDOW = max(before for _label, before in REMINDERS)


@dataclass
class DueItem:
    application_id: PydanticObjectId
    key: str
    company: str
    role: str
    deadline: datetime
    application_url: str | None


async def _candidates(now: datetime) -> list[tuple[Application, Opportunity, datetime]]:
    """Applications whose deadline (their own, or the posting's) is inside the widest
    reminder window."""
    horizon = now + WINDOW
    own = await Application.find(Application.deadline > now, Application.deadline <= horizon).to_list()
    # Applications saved before per-student deadlines existed only have the posting's.
    closing = await Opportunity.find(Opportunity.deadline > now, Opportunity.deadline <= horizon).to_list()
    inherited = (
        await Application.find(
            {"opportunity_id": {"$in": [o.id for o in closing]}, "deadline": None}
        ).to_list()
        if closing
        else []
    )
    opportunities = {o.id: o for o in closing}
    missing = {a.opportunity_id for a in own} - opportunities.keys()
    if missing:
        for o in await Opportunity.find({"_id": {"$in": list(missing)}}).to_list():
            opportunities[o.id] = o
    out = []
    for application in own + inherited:
        opportunity = opportunities.get(application.opportunity_id)
        if opportunity is not None:
            out.append((application, opportunity, application.deadline or opportunity.deadline))
    return out


async def _claim(application_id: PydanticObjectId, key: str) -> bool:
    result = await Application.get_motor_collection().update_one(
        {"_id": application_id, "reminders_sent": {"$ne": key}}, {"$addToSet": {"reminders_sent": key}}
    )
    return result.modified_count == 1


async def _release(items: list[DueItem]) -> None:
    for item in items:
        await Application.get_motor_collection().update_one(
            {"_id": item.application_id}, {"$pull": {"reminders_sent": item.key}}
        )


def compose(items: list[DueItem], now: datetime) -> tuple[str, str]:
    """(subject, body) for one student's reminder email."""
    items = sorted(items, key=lambda i: i.deadline)
    first = items[0]
    if len(items) == 1:
        subject = f"Closes in {time_left(first.deadline, now)}: {first.role} at {first.company}"
    else:
        subject = f"{len(items)} applications close soon, the first in {time_left(first.deadline, now)}"
    base = settings.FRONTEND_URL.rstrip("/")
    lines = ["These close soon and you haven't applied yet:", ""]
    for item in items:
        lines.append(f"- {item.role} at {item.company}")
        lines.append(f"  Closes {format_ist(item.deadline)} (in {time_left(item.deadline, now)})")
        if item.application_url:
            lines.append(f"  Apply: {item.application_url}")
        lines.append(f"  In Pathlight: {base}/applications/{item.application_id}")
        lines.append("")
    lines.append(
        "You get these 24 hours and 3 hours before a deadline. "
        f"Turn them off under Deadline reminders in your profile: {base}/profile"
    )
    return subject, "\n".join(lines)


async def run_deadline_reminders_once(now: datetime | None = None) -> int:
    """Sends every reminder that is due. Returns how many emails went out. Never raises
    for one student's failure: the rest still get theirs."""
    if not mail_configured():
        return 0
    now = now or datetime.now(timezone.utc)
    by_user: dict[PydanticObjectId, list[DueItem]] = {}
    companies: dict[PydanticObjectId, str] = {}
    for application, opportunity, deadline in await _candidates(now):
        if not is_open([e.stage.value for e in application.status_history]):
            continue
        label = reminder_due(deadline, application.reminders_sent, now)
        if label is None:
            continue
        if opportunity.company_id not in companies:
            company = await Company.get(opportunity.company_id)
            companies[opportunity.company_id] = company.name if company else "Unknown company"
        req = opportunity.requirements
        by_user.setdefault(application.user_id, []).append(
            DueItem(
                application_id=application.id,
                key=reminder_key(label, deadline),
                company=companies[opportunity.company_id],
                role=opportunity.role,
                deadline=deadline,
                application_url=req.application_url if req else None,
            )
        )

    sent = 0
    for user_id, items in by_user.items():
        profile = await Profile.find_one(Profile.user_id == user_id)
        if profile is not None and not profile.deadline_reminders:
            continue
        user = await User.get(user_id)
        if user is None:
            continue
        claimed = [item for item in items if await _claim(item.application_id, item.key)]
        if not claimed:
            continue
        subject, body = compose(claimed, now)
        try:
            await send_mail(user.email, subject, body)
            sent += 1
        except Exception:
            # Un-claim, so the next hourly run tries again while the window is still open.
            logger.exception("deadline reminder failed for %s", user_id)
            await _release(claimed)
    return sent
