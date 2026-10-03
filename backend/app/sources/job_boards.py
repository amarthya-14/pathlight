"""
Job boards — opportunities from the open web, not just the user's inbox.

Only official, public JSON APIs are used — no scraping, no logins:
- Public job-board APIs of applicant-tracking systems (Greenhouse, Lever, Ashby,
  SmartRecruiters) for a curated list of companies hiring engineers in India — the same
  endpoints the companies' own careers pages read from. Mostly experienced roles.
- Adzuna and Jooble (India) — job aggregators with official APIs and the best source of
  FRESHER roles. Each needs a free key (ADZUNA_APP_ID/ADZUNA_APP_KEY, JOOBLE_API_KEY);
  without one that source is simply skipped.
- Remotive, Himalayas and Arbeitnow remote-job APIs (published for exactly this use).

Each fetcher returns normalized dicts; app/models/job_listing.py stores them and
app/api/routes/jobs.py ranks them per user. A source that fails is skipped — one board
being down must never empty the feed.
"""
import asyncio
import html
import logging
import re
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Verified reachable with Indian openings on 2026-10-03 (probed ~400 companies across six
# ATS APIs). Board tokens are the company's own identifier on the ATS; a company that
# moves ATS just starts returning 404 and is skipped.
GREENHOUSE_BOARDS = [
    "groww", "druva", "hackerrank", "inmobi", "sigmoid", "rubrik", "databricks", "devrev",
    "highradius", "observeai", "glance", "zenoti", "stripe", "cloudflare", "mongodb", "elastic",
    "gitlab", "twilio", "okta", "zscaler", "samsara", "fivetran", "grafanalabs", "coinbase",
    "airbnb", "newrelic", "datadog", "yugabyte", "neo4j", "agoda", "roblox", "saucelabs", "anthropic",
]
LEVER_BOARDS = ["meesho", "cred", "paytm", "zeta", "mindtickle", "pocketfm", "hevodata", "linkedin"]
ASHBY_BOARDS = ["sarvam", "atlan", "openai", "notion", "snowflake", "redis"]
SMARTRECRUITERS_BOARDS = ["swiggy", "freshworks", "mindtickle", "ixigo", "servicenow", "wise", "unacademy", "canva"]

# Aggregator searches: what students actually look for. Users' own target roles are
# added to these at refresh time (see app/api/routes/jobs.py).
DEFAULT_QUERIES = [
    "software engineer fresher", "software developer", "backend developer", "frontend developer",
    "full stack developer", "data analyst fresher", "machine learning engineer", "graduate engineer trainee",
]

TECH_TITLE = re.compile(
    r"\b(engineer|engineering|developer|software|sde|swe|programmer|data|machine learning|ml|ai|"
    r"analyst|backend|back-end|frontend|front-end|full[- ]?stack|devops|sre|cloud|qa|test|security|"
    r"mobile|android|ios|web|platform|infrastructure|intern|graduate|trainee)\b",
    re.I,
)
INDIA = re.compile(
    r"\b(india|bengaluru|bangalore|hyderabad|pune|mumbai|chennai|gurgaon|gurugram|noida|delhi|"
    r"kolkata|ahmedabad|kochi|coimbatore|jaipur|indore|chandigarh|trivandrum|vizag|visakhapatnam)\b",
    re.I,
)
ANYWHERE = re.compile(r"\b(anywhere|worldwide|global|apac|asia)\b", re.I)

TIMEOUT = httpx.Timeout(20.0, connect=8.0)
HEADERS = {"User-Agent": "Pathlight/1.0 (student career assistant)"}


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = html.unescape(raw)  # Greenhouse double-escapes its HTML
    text = re.sub(r"<\s*(br|/p|/li|/h\d|/div)\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<\s*li[^>]*>", "\n• ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _listing(source, external_id, title, company, location, remote, url, description, posted_at=None, tags=None):
    return {
        "source": source,
        "external_id": str(external_id),
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (location or "").strip() or ("Remote" if remote else ""),
        "remote": bool(remote),
        "url": url,
        "description": (description or "")[:12000],
        "tags": tags or [],
        "posted_at": posted_at,
    }


def relevant(listing: dict) -> bool:
    """Tech roles a student in India can actually take: located in India, or remote and
    open to anywhere/Asia (a "Remote — US only" role isn't an opportunity for them)."""
    if not listing["title"] or not listing["url"] or not TECH_TITLE.search(listing["title"]):
        return False
    location = listing["location"]
    if INDIA.search(location):
        return True
    return listing["remote"] and (not location or bool(ANYWHERE.search(location)) or bool(INDIA.search(location)))


def _ts(value) -> datetime | None:
    try:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)) or str(value).isdigit():
            v = float(value)
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


async def _greenhouse(client: httpx.AsyncClient, board: str) -> list[dict]:
    r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"})
    r.raise_for_status()
    out = []
    for job in r.json().get("jobs", []):
        location = (job.get("location") or {}).get("name", "")
        out.append(
            _listing(
                "greenhouse", f"{board}:{job['id']}", job.get("title"), job.get("company_name") or board.title(),
                location, "remote" in location.lower(), job.get("absolute_url"),
                html_to_text(job.get("content")), _ts(job.get("first_published") or job.get("updated_at")),
            )
        )
    return out


async def _lever(client: httpx.AsyncClient, board: str) -> list[dict]:
    r = await client.get(f"https://api.lever.co/v0/postings/{board}", params={"mode": "json"})
    r.raise_for_status()
    out = []
    for job in r.json():
        cats = job.get("categories") or {}
        location = cats.get("location") or ""
        if job.get("country") == "IN" and not INDIA.search(location):
            location = f"{location}, India".strip(", ")
        lists = "\n".join(
            f"{block.get('text', '')}\n{html_to_text(block.get('content'))}" for block in job.get("lists") or []
        )
        out.append(
            _listing(
                "lever", f"{board}:{job['id']}", job.get("text"), board.title(), location,
                job.get("workplaceType") == "remote", job.get("hostedUrl"),
                f"{job.get('descriptionPlain') or ''}\n{lists}\n{job.get('additionalPlain') or ''}",
                _ts(job.get("createdAt")),
            )
        )
    return out


async def _remotive(client: httpx.AsyncClient) -> list[dict]:
    r = await client.get("https://remotive.com/api/remote-jobs", params={"category": "software-dev", "limit": 150})
    r.raise_for_status()
    return [
        _listing(
            "remotive", job["id"], job.get("title"), job.get("company_name"),
            job.get("candidate_required_location") or "Worldwide", True, job.get("url"),
            html_to_text(job.get("description")), _ts(job.get("publication_date")), job.get("tags"),
        )
        for job in r.json().get("jobs", [])
    ]


async def _himalayas(client: httpx.AsyncClient) -> list[dict]:
    out = []
    for offset in (0, 20, 40):
        r = await client.get("https://himalayas.app/jobs/api", params={"limit": 20, "offset": offset})
        r.raise_for_status()
        for job in r.json().get("jobs", []):
            restrictions = job.get("locationRestrictions") or []
            out.append(
                _listing(
                    "himalayas", job.get("guid") or job.get("applicationLink"), job.get("title"),
                    job.get("companyName"), ", ".join(restrictions) or "Worldwide", True,
                    job.get("applicationLink"), html_to_text(job.get("description")),
                    _ts(job.get("pubDate")), job.get("categories"),
                )
            )
    return out


async def _arbeitnow(client: httpx.AsyncClient) -> list[dict]:
    r = await client.get("https://www.arbeitnow.com/api/job-board-api")
    r.raise_for_status()
    return [
        _listing(
            "arbeitnow", job["slug"], job.get("title"), job.get("company_name"), job.get("location"),
            bool(job.get("remote")), job.get("url"), html_to_text(job.get("description")),
            _ts(job.get("created_at")), job.get("tags"),
        )
        for job in r.json().get("data", [])
    ]


async def _ashby(client: httpx.AsyncClient, board: str) -> list[dict]:
    r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    r.raise_for_status()
    out = []
    for job in r.json().get("jobs", []):
        if job.get("isListed") is False:
            continue
        address = ((job.get("address") or {}).get("postalAddress") or {})
        location = job.get("location") or ""
        country = address.get("addressCountry")
        if country and country.lower() not in location.lower():
            location = f"{location}, {country}".strip(", ")
        out.append(
            _listing(
                "ashby", f"{board}:{job['id']}", job.get("title"), board.title(), location,
                bool(job.get("isRemote")), job.get("jobUrl"), job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml")),
                _ts(job.get("publishedAt")),
            )
        )
    return out


async def _smartrecruiters(client: httpx.AsyncClient, board: str) -> list[dict]:
    """The list endpoint has no descriptions; details are fetched only for postings that
    pass the cheap filters (tech title, India/remote), capped per company."""
    base = f"https://api.smartrecruiters.com/v1/companies/{board}/postings"
    postings: list[dict] = []
    for offset in (0, 100):
        r = await client.get(base, params={"limit": 100, "offset": offset})
        r.raise_for_status()
        page = r.json().get("content", [])
        postings += page
        if len(page) < 100:
            break
    out = []
    candidates = []
    for job in postings:
        loc = job.get("location") or {}
        location = ", ".join(p for p in [loc.get("city"), loc.get("region"), "India" if loc.get("country") == "in" else loc.get("country")] if p)
        listing = _listing(
            "smartrecruiters", f"{board}:{job['id']}", job.get("name"), (job.get("company") or {}).get("name") or board.title(),
            location, bool(loc.get("remote")), f"https://jobs.smartrecruiters.com/{board}/{job['id']}", "",
            _ts(job.get("releasedDate")),
        )
        if relevant(listing):
            candidates.append((job["id"], listing))
    sem = asyncio.Semaphore(8)

    async def detail(job_id: str, listing: dict) -> dict:
        async with sem:
            try:
                d = (await client.get(f"{base}/{job_id}")).json()
                sections = (d.get("jobAd") or {}).get("sections") or {}
                listing["description"] = "\n\n".join(
                    html_to_text((sections.get(k) or {}).get("text"))
                    for k in ("jobDescription", "qualifications", "additionalInformation")
                )[:12000]
                listing["url"] = d.get("postingUrl") or listing["url"]
            except Exception:
                pass  # keep the listing with its title; skills just come out thinner
            return listing

    out = await asyncio.gather(*(detail(job_id, listing) for job_id, listing in candidates[:60]))
    return list(out)


async def _adzuna(client: httpx.AsyncClient, queries: list[str]) -> list[dict]:
    """Adzuna India (official API, free key). Descriptions are ~500-char snippets."""
    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        raise SourceDisabled("set ADZUNA_APP_ID and ADZUNA_APP_KEY")
    out = []
    for query in queries:
        for page in (1, 2):
            r = await client.get(
                f"https://api.adzuna.com/v1/api/jobs/in/search/{page}",
                params={
                    "app_id": settings.ADZUNA_APP_ID, "app_key": settings.ADZUNA_APP_KEY, "what": query,
                    "results_per_page": 50, "max_days_old": 45, "sort_by": "date", "content-type": "application/json",
                },
            )
            r.raise_for_status()
            for job in r.json().get("results", []):
                location = (job.get("location") or {}).get("display_name") or "India"
                if "india" not in location.lower():
                    location = f"{location}, India"
                out.append(
                    _listing(
                        "adzuna", job["id"], job.get("title"), (job.get("company") or {}).get("display_name"), location,
                        False, job.get("redirect_url"), html_to_text(job.get("description")), _ts(job.get("created")),
                    )
                )
    return out


async def _jooble(client: httpx.AsyncClient, queries: list[str]) -> list[dict]:
    """Jooble India (official API, free key on request). Descriptions are snippets."""
    if not settings.JOOBLE_API_KEY:
        raise SourceDisabled("set JOOBLE_API_KEY")
    out = []
    for query in queries:
        r = await client.post(f"https://jooble.org/api/{settings.JOOBLE_API_KEY}", json={"keywords": query, "location": "India", "page": 1})
        r.raise_for_status()
        for job in r.json().get("jobs", []):
            location = job.get("location") or "India"
            if "india" not in location.lower():
                location = f"{location}, India"
            out.append(
                _listing(
                    "jooble", job.get("id") or job.get("link"), job.get("title"), job.get("company"), location,
                    "remote" in (job.get("type") or "").lower(), job.get("link"), html_to_text(job.get("snippet")),
                    _ts(job.get("updated")),
                )
            )
    return out


class SourceDisabled(Exception):
    """A source that needs configuration (an API key) the server doesn't have."""


async def fetch_all(queries: list[str] | None = None) -> tuple[list[dict], dict[str, str]]:
    """Fetches every source concurrently. Returns (relevant listings, per-source status)."""
    queries = list(dict.fromkeys((queries or []) + DEFAULT_QUERIES))[:14]
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        tasks: dict[str, asyncio.Task] = {}
        for board in GREENHOUSE_BOARDS:
            tasks[f"greenhouse:{board}"] = asyncio.create_task(_greenhouse(client, board))
        for board in LEVER_BOARDS:
            tasks[f"lever:{board}"] = asyncio.create_task(_lever(client, board))
        for board in ASHBY_BOARDS:
            tasks[f"ashby:{board}"] = asyncio.create_task(_ashby(client, board))
        for board in SMARTRECRUITERS_BOARDS:
            tasks[f"smartrecruiters:{board}"] = asyncio.create_task(_smartrecruiters(client, board))
        tasks["adzuna"] = asyncio.create_task(_adzuna(client, queries))
        tasks["jooble"] = asyncio.create_task(_jooble(client, queries))
        tasks["remotive"] = asyncio.create_task(_remotive(client))
        tasks["himalayas"] = asyncio.create_task(_himalayas(client))
        tasks["arbeitnow"] = asyncio.create_task(_arbeitnow(client))
        await asyncio.gather(*tasks.values(), return_exceptions=True)

    listings: list[dict] = []
    status: dict[str, str] = {}
    for name, task in tasks.items():
        exc = task.exception()
        if isinstance(exc, SourceDisabled):
            status[name] = f"off ({exc})"
            continue
        if exc is not None:
            status[name] = f"error: {type(exc).__name__}"
            logger.info("job source %s failed: %s", name, exc)
            continue
        found = [l for l in task.result() if relevant(l)]
        status[name] = f"ok ({len(found)})"
        listings.extend(found)
    return dedupe(listings), status


def dedupe(listings: list[dict]) -> list[dict]:
    """Same role at the same company listed per city (or on two aggregators) -> one row,
    keeping the first (company boards are fetched first, so the direct link wins) with
    every location merged."""
    seen: dict[tuple[str, str], dict] = {}
    for listing in listings:
        key = (re.sub(r"\W+", "", listing["company"].lower()), re.sub(r"\W+", "", listing["title"].lower()))
        if key in seen:
            first = seen[key]
            if listing["location"] and listing["location"] not in first["location"] and len(first["location"]) < 120:
                first["location"] = f"{first['location']} · {listing['location']}"
            continue
        seen[key] = listing
    return list(seen.values())
