"""
Job boards — opportunities from the open web, not just the user's inbox.

Only official, public JSON APIs are used — no scraping, no logins:
- Public job-board APIs of applicant-tracking systems (Greenhouse, Lever, Ashby,
  SmartRecruiters) for a curated list of companies hiring engineers in India — the same
  endpoints the companies' own careers pages read from. Mostly experienced roles.
- Adzuna and Jooble (India) — job aggregators with official APIs and the best source of
  FRESHER roles. Each needs a free key (ADZUNA_APP_ID/ADZUNA_APP_KEY, JOOBLE_API_KEY);
  without one that source is simply skipped.
- Remotive, Himalayas, Jobicy and Arbeitnow remote-job APIs (published for exactly this
  use), and The Muse's public API for internships and entry-level roles in India.

search_web() runs one student's search live on the sources that take a keyword, so a
search isn't limited to what the twice-daily refresh happened to fetch.

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
    "software engineer intern", "data science intern", "web developer intern", "part time developer",
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


def _listing(source, external_id, title, company, location, remote, url, description, posted_at=None, tags=None, employment=""):
    """employment: the board's own job-type field, if any ("Intern", "FullTime") — read by
    job_signals.job_type() at refresh time, not stored."""
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
        "employment": employment or "",
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
                _ts(job.get("createdAt")), employment=cats.get("commitment") or "",
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
            employment=job.get("job_type") or "",
        )
        for job in r.json().get("jobs", [])
    ]


def _himalayas_job(job: dict) -> dict:
    restrictions = job.get("locationRestrictions") or []
    return _listing(
        "himalayas", job.get("guid") or job.get("applicationLink"), job.get("title"),
        job.get("companyName"), ", ".join(restrictions) or "Worldwide", True,
        job.get("applicationLink"), html_to_text(job.get("description")),
        _ts(job.get("pubDate")), job.get("categories"), employment=job.get("employmentType") or "",
    )


async def _himalayas(client: httpx.AsyncClient) -> list[dict]:
    out = []
    for offset in (0, 20, 40):
        r = await client.get("https://himalayas.app/jobs/api", params={"limit": 20, "offset": offset})
        r.raise_for_status()
        out += [_himalayas_job(job) for job in r.json().get("jobs", [])]
    return out


def _jobicy_job(job: dict) -> dict:
    return _listing(
        "jobicy", job["id"], html.unescape(job.get("jobTitle") or ""), html.unescape(job.get("companyName") or ""),
        job.get("jobGeo") or "Anywhere", True, job.get("url"), html_to_text(job.get("jobDescription")),
        _ts(job.get("pubDate")), job.get("jobIndustry"), employment=", ".join(job.get("jobType") or []),
    )


async def _jobicy(client: httpx.AsyncClient, tag: str | None = None) -> list[dict]:
    params = {"count": 50, **({"tag": tag} if tag else {"industry": "dev"})}
    r = await client.get("https://jobicy.com/api/v2/remote-jobs", params=params)
    r.raise_for_status()
    return [_jobicy_job(job) for job in r.json().get("jobs", [])]


MUSE_CATEGORIES = ["Software Engineering", "Data and Analytics", "Data Science", "IT"]


async def _themuse(client: httpx.AsyncClient, levels: tuple[str, ...] = ("Internship", "Entry Level")) -> list[dict]:
    """The Muse — internships and entry-level roles in India or flexible/remote."""
    params = [("level", level) for level in levels] + [("category", c) for c in MUSE_CATEGORIES]
    params += [("location", "India"), ("location", "Flexible / Remote")]
    out = []
    for page in (0, 1):
        r = await client.get("https://www.themuse.com/api/public/jobs", params=params + [("page", page)])
        r.raise_for_status()
        data = r.json()
        for job in data.get("results", []):
            locations = [l.get("name", "") for l in job.get("locations") or []]
            india = [l for l in locations if INDIA.search(l)]
            remote = any("remote" in l.lower() or "flexible" in l.lower() for l in locations)
            levels_ = " ".join(l.get("name", "") for l in job.get("levels") or [])
            out.append(
                _listing(
                    "themuse", job["id"], job.get("name"), (job.get("company") or {}).get("name"),
                    " · ".join(india) or ("Worldwide" if remote else ", ".join(locations)), remote and not india,
                    (job.get("refs") or {}).get("landing_page"), html_to_text(job.get("contents")),
                    _ts(job.get("publication_date")), employment="Intern" if "Internship" in levels_ else "",
                )
            )
        if page + 1 >= data.get("page_count", 0):
            break
    return out


async def _arbeitnow(client: httpx.AsyncClient) -> list[dict]:
    r = await client.get("https://www.arbeitnow.com/api/job-board-api")
    r.raise_for_status()
    return [
        _listing(
            "arbeitnow", job["slug"], job.get("title"), job.get("company_name"), job.get("location"),
            bool(job.get("remote")), job.get("url"), html_to_text(job.get("description")),
            _ts(job.get("created_at")), job.get("tags"), employment=", ".join(job.get("job_types") or []),
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
                _ts(job.get("publishedAt")), employment=job.get("employmentType") or "",
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
            _ts(job.get("releasedDate")), employment=(job.get("typeOfEmployment") or {}).get("label") or "",
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


async def _adzuna(client: httpx.AsyncClient, queries: list[str], pages: tuple[int, ...] = (1, 2)) -> list[dict]:
    """Adzuna India (official API, free key). Descriptions are ~500-char snippets."""
    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        raise SourceDisabled("set ADZUNA_APP_ID and ADZUNA_APP_KEY")
    out = []
    for query in queries:
        for page in pages:
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
                        employment=" ".join(filter(None, [job.get("contract_time"), job.get("contract_type")])),
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
                    _ts(job.get("updated")), employment=job.get("type") or "",
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
        tasks["jobicy"] = asyncio.create_task(_jobicy(client))
        tasks["themuse"] = asyncio.create_task(_themuse(client))
        await asyncio.gather(*tasks.values(), return_exceptions=True)
    return _collect(tasks)


# Words that say which job type a search wants — the type itself is a feed filter, so
# they're stripped from the keywords and re-added in each source's own vocabulary.
TYPE_WORDS = re.compile(r"\b(internships?|interns?|full[- ]?time|part[- ]?time|jobs?|roles?|openings?)\b", re.I)
_TYPE_SUFFIX = {"internship": "intern", "part_time": "part time", "full_time": "", "contract": "contract"}


def search_keywords(query: str) -> str:
    return re.sub(r"\s+", " ", TYPE_WORDS.sub(" ", query or "")).strip()


async def _himalayas_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    out = []
    for page in (1, 2):
        r = await client.get("https://himalayas.app/jobs/api/search", params={"q": query, "page": page})
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        out += [_himalayas_job(job) for job in jobs]
        if len(jobs) < 20:
            break
    return out


async def _remotive_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    r = await client.get("https://remotive.com/api/remote-jobs", params={"search": query, "limit": 100})
    r.raise_for_status()
    return [
        _listing(
            "remotive", job["id"], job.get("title"), job.get("company_name"),
            job.get("candidate_required_location") or "Worldwide", True, job.get("url"),
            html_to_text(job.get("description")), _ts(job.get("publication_date")), job.get("tags"),
            employment=job.get("job_type") or "",
        )
        for job in r.json().get("jobs", [])
    ]


async def search_web(query: str, job_type: str | None = None) -> tuple[list[dict], dict[str, str]]:
    """One student's search, run live on every source that takes a keyword (plus The
    Muse's internship/entry-level feed when they want internships). Same relevance and
    dedupe rules as the scheduled refresh."""
    keywords = search_keywords(query)
    suffix = _TYPE_SUFFIX.get(job_type or "", "")
    phrase = f"{keywords} {suffix}".strip() or "software engineer"
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        tasks: dict[str, asyncio.Task] = {
            "adzuna": asyncio.create_task(_adzuna(client, [phrase], pages=(1,))),
            "jooble": asyncio.create_task(_jooble(client, [phrase])),
            "himalayas": asyncio.create_task(_himalayas_search(client, phrase)),
            "remotive": asyncio.create_task(_remotive_search(client, keywords or phrase)),
            "jobicy": asyncio.create_task(_jobicy(client, tag=keywords or None)),
        }
        if job_type in (None, "", "internship"):
            levels = ("Internship",) if job_type == "internship" else ("Internship", "Entry Level")
            tasks["themuse"] = asyncio.create_task(_themuse(client, levels))
        await asyncio.gather(*tasks.values(), return_exceptions=True)
    return _collect(tasks)


def _collect(tasks: dict[str, asyncio.Task]) -> tuple[list[dict], dict[str, str]]:
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
