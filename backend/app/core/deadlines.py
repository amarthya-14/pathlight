"""
Deadlines across sources — the "deadline digest" (reports: upgrade #2).

One campus drive often reaches a student three times: the portal's own email (Superset,
Unstop), the T&P cell's email, and a forwarded WhatsApp message. The pipeline already
dedupes the posting (company + role_hash); this module decides what its deadline is when
those copies disagree, and when to remind the student before it passes. Colleges put
missed notices on the student ("deadlines will not be extended"), so the rules here
lean towards the earlier time.

All deterministic — no LLM decides a deadline or a reminder.
"""
import re
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

# Widest first. A reminder fires once per window, the first time the deadline is inside it.
REMINDERS = (("24h", timedelta(hours=24)), ("3h", timedelta(hours=3)))

# Once a student has applied, skipped, or moved past applying, the deadline no longer
# needs their attention.
DONE_STAGES = {"APPLIED", "OA", "INTERVIEW", "OFFER", "REJECTED", "SKIPPED_BY_USER"}


def normalize_deadline(value: datetime | None) -> datetime | None:
    """A deadline with no time zone is Indian time: placement notices say "5 PM" and mean
    IST. Treating it as UTC (the old behaviour) put every such deadline 5.5 hours late."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(timezone.utc)


def merge_deadline(current: datetime | None, incoming: datetime | None, now: datetime | None = None) -> datetime | None:
    """The deadline to keep when a second copy of the same drive arrives. Keeps the
    earlier one, unless the earlier one has already passed and the new one hasn't — a
    later notice for a closed drive means it was extended or reopened."""
    current, incoming = normalize_deadline(current), normalize_deadline(incoming)
    if current is None or incoming is None:
        return current or incoming
    now = now or datetime.now(timezone.utc)
    earlier, later = sorted((current, incoming))
    if earlier <= now < later:
        return later
    return earlier


def is_open(stages: list[str]) -> bool:
    """True while the student still has to act before the deadline."""
    return not any(stage in DONE_STAGES for stage in stages)


def reminder_key(label: str, deadline: datetime) -> str:
    # Keyed on the deadline itself, so a changed deadline re-arms its reminders.
    return f"{label}@{normalize_deadline(deadline).isoformat()}"


def reminder_due(deadline: datetime, sent: list[str], now: datetime | None = None) -> str | None:
    """The reminder to send now ("24h" or "3h"), or None. Only the tightest window the
    deadline is in counts: a drive found 2 hours before it closes gets the 3h reminder,
    not both."""
    deadline = normalize_deadline(deadline)
    now = now or datetime.now(timezone.utc)
    left = deadline - now
    if left <= timedelta(0):
        return None
    due = None
    for label, before in REMINDERS:
        if left <= before:
            due = label
    if due is None or reminder_key(due, deadline) in sent:
        return None
    return due


def format_ist(deadline: datetime) -> str:
    return normalize_deadline(deadline).astimezone(IST).strftime("%a %d %b, %I:%M %p IST")


def time_left(deadline: datetime, now: datetime | None = None) -> str:
    left = normalize_deadline(deadline) - (now or datetime.now(timezone.utc))
    hours = max(int(left.total_seconds() // 3600), 0)
    if hours < 1:
        return "under an hour"
    if hours < 48:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{hours // 24} days"


# A message copied out of WhatsApp keeps its header: "[22/10/26, 4:05 pm] TPO Sir: ..."
# (or "22/10/26, 4:05 pm - TPO Sir: ..." in a chat export).
_WHATSAPP_LINE = re.compile(
    r"^\[?\d{1,2}/\d{1,2}(?:/\d{2,4})?,?\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]\.?\s?m\.?)?\]?\s*(?:-\s*)?[^:\n]{1,60}:",
    re.IGNORECASE | re.MULTILINE,
)


def looks_like_whatsapp(text: str) -> bool:
    return bool(_WHATSAPP_LINE.search(text or ""))
