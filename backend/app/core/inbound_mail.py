"""
Parsing for forwarded mail: raw MIME (what Cloudflare Email Workers and most inbound
services deliver) into sender / recipient / subject / readable text, and recognising the
two kinds Pathlight acts on: job alerts, and Gmail's forwarding-confirmation email.
"""
import hashlib
import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr

from app.sources.job_boards import html_to_text

GMAIL_CONFIRMATION_SENDER = "forwarding-noreply@google.com"
# Job-alert senders accepted from forwarding (domains, so new LinkedIn/Naukri sender
# addresses keep working).
ALERT_DOMAINS = ("linkedin.com", "naukri.com", "naukrialerts.com", "indeed.com", "instahyre.com", "foundit.in",
                 "internshala.com", "wellfound.com", "cutshort.io", "glassdoor.com", "glassdoor.co.in")


@dataclass
class ParsedMail:
    sender: str
    recipients: list[str]
    subject: str
    text: str
    message_id: str

    @property
    def fingerprint(self) -> str:
        basis = self.message_id or f"{self.sender}|{self.subject}|{self.text[:500]}"
        return hashlib.sha256(basis.encode("utf-8", "ignore")).hexdigest()


def parse_mime(raw: bytes, envelope_to: str | None = None) -> ParsedMail:
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    sender = parseaddr(str(msg.get("From", "")))[1].lower()
    recipients = [a.lower() for _, a in getaddresses(
        [str(msg.get(h, "")) for h in ("Delivered-To", "X-Original-To", "To", "Cc")]
    ) if a]
    if envelope_to:
        recipients.insert(0, envelope_to.strip().lower())
    text = ""
    plain = msg.get_body(preferencelist=("plain",))
    html = msg.get_body(preferencelist=("html",))
    if plain is not None:
        text = plain.get_content()
    if (not text.strip() or len(text) < 200) and html is not None:
        text = html_to_text(html.get_content()) or text
    return ParsedMail(
        sender=sender,
        recipients=list(dict.fromkeys(recipients)),
        subject=str(msg.get("Subject", "")).strip(),
        text=text.strip(),
        message_id=str(msg.get("Message-ID", "")).strip(),
    )


def token_for(recipients: list[str], domain: str) -> str | None:
    """The student token in the first recipient at our inbound domain (plus-tags ignored)."""
    domain = domain.lower().lstrip("@")
    for address in recipients:
        local, _, host = address.partition("@")
        if host == domain and local:
            return local.split("+", 1)[0]
    return None


def is_gmail_confirmation(mail: ParsedMail) -> bool:
    return mail.sender == GMAIL_CONFIRMATION_SENDER


def gmail_confirmation(mail: ParsedMail) -> tuple[str | None, str | None]:
    code = re.search(r"Confirmation code:\s*(\d{6,12})", mail.text)
    link = re.search(r"https://mail(?:-settings)?\.google\.com/mail/[^\s\"'<>]+", mail.text)
    return (code.group(1) if code else None), (link.group(0) if link else None)


def is_job_alert(mail: ParsedMail) -> bool:
    host = mail.sender.rpartition("@")[2]
    return any(host == d or host.endswith("." + d) for d in ALERT_DOMAINS)
