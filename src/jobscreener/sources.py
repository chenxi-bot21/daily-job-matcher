"""
Job-posting sources (the *LinkedIn* step in the workflow).

A source returns a list of **raw** posting dicts; :mod:`jobscreener.normalize`
standardises them. The default is a bundled JSON file so the pipeline runs fully
offline and deterministically. Real sources are pluggable behind the same
interface.

A note on LinkedIn: scraping LinkedIn violates its Terms of Service and is
brittle against anti-bot measures, so this project does **not** ship a scraper.
Use LinkedIn's official partner APIs, an ATS/job-board API (Adzuna, Greenhouse,
Remotive), or export postings to the JSON schema in ``data/sample_jobs.json``.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Protocol


class JobSource(Protocol):
    name: str

    def fetch(self) -> list[dict]: ...


class SampleFileSource:
    """Read raw postings from a JSON file (the default, offline source)."""

    name = "sample_file"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self) -> list[dict]:
        if not self.path.exists():
            raise FileNotFoundError(f"Job file not found: {self.path}")
        return json.loads(self.path.read_text(encoding="utf-8"))


def _coerce_str(value) -> str:
    """Coerce a possibly-NaN / non-string cell (from a DataFrame) to a clean str."""
    if value is None:
        return ""
    if isinstance(value, float):  # pandas NaN is a float
        return "" if value != value else str(value)
    return str(value)


def _days_since(date_posted) -> int:
    """Days between a posting date (date/datetime/ISO string) and today; 0 if unknown."""
    import datetime as _dt

    if date_posted is None or (isinstance(date_posted, float) and date_posted != date_posted):
        return 0
    try:
        if isinstance(date_posted, _dt.datetime):
            d = date_posted.date()
        elif isinstance(date_posted, _dt.date):
            d = date_posted
        else:
            d = _dt.date.fromisoformat(str(date_posted)[:10])
        return max((_dt.date.today() - d).days, 0)
    except (ValueError, TypeError):
        return 0


def map_jobspy_row(row: dict) -> dict:
    """Map one JobSpy DataFrame row (as a dict) to our raw schema. Pure/testable."""
    return {
        "title": _coerce_str(row.get("title")),
        "company": _coerce_str(row.get("company")),
        "location": _coerce_str(row.get("location")),
        "description": _coerce_str(row.get("description")),
        "url": _coerce_str(row.get("job_url") or row.get("job_url_direct")),
        "posted_days_ago": _days_since(row.get("date_posted")),
        "employment_type": _coerce_str(row.get("job_type")),
        "source": "jobspy/" + _coerce_str(row.get("site")),
    }


class JobSpyCsvSource:
    """Ingest a CSV that JobSpy already produced (``scrape_jobs(...).to_csv()``).

    Lets you run the scraping yourself, whenever/wherever you like, and have this
    tool only *rank* the results — no scraping happens from here.
    """

    name = "jobspy_csv"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self) -> list[dict]:
        import csv

        if not self.path.exists():
            raise FileNotFoundError(f"CSV not found: {self.path}")
        with open(self.path, encoding="utf-8", newline="") as f:
            return [map_jobspy_row(row) for row in csv.DictReader(f)]


class JobSpySource:
    """Aggregate postings across job boards via JobSpy (no API key; a scraper).

    Requires ``pip install python-jobspy``. Scrapes LinkedIn/Indeed/Glassdoor/etc.
    into a DataFrame, which we map to our schema. Indeed rarely rate-limits;
    LinkedIn does — pass ``proxies`` if you scrape it heavily.
    """

    name = "jobspy"

    def __init__(self, search: str = "analyst", location: str = "",
                 sites: list[str] | None = None, country: str = "usa",
                 results: int = 80, hours_old: int = 504, proxies: list[str] | None = None):
        self.search = search
        self.location = location
        self.sites = sites or ["linkedin", "indeed", "glassdoor"]
        self.country = country or "usa"
        self.results = results
        self.hours_old = hours_old            # 504h = 21 days
        self.proxies = proxies

    def fetch(self) -> list[dict]:  # pragma: no cover - network scraping
        import inspect

        from jobspy import scrape_jobs

        # scrape_jobs' signature drifts between JobSpy versions; only pass
        # arguments the installed version actually accepts.
        supported = set(inspect.signature(scrape_jobs).parameters)
        kwargs = {
            "site_name": self.sites,
            "search_term": self.search,
            "location": self.location,
            "results_wanted": self.results,
            "country_indeed": self.country,
        }
        if "hours_old" in supported:
            kwargs["hours_old"] = self.hours_old
        if "linkedin_fetch_description" in supported:
            kwargs["linkedin_fetch_description"] = True
        if self.proxies:
            if "proxies" in supported:
                kwargs["proxies"] = self.proxies
            elif "proxy" in supported:
                kwargs["proxy"] = self.proxies

        df = scrape_jobs(**kwargs)
        if df is None or len(df) == 0:
            return []
        return [map_jobspy_row(r) for r in df.to_dict("records")]


def map_apify_item(item: dict) -> dict:
    """Map one Apify LinkedIn-scraper dataset item to our raw schema.

    Pure and unit-testable; tolerant of the field-name differences between the
    various LinkedIn-jobs actors on Apify.
    """
    def first(*keys):
        for k in keys:
            v = item.get(k)
            if v:
                return v
        return ""

    return {
        "title": first("title", "jobTitle", "position"),
        "company": first("companyName", "company", "company_name"),
        "location": first("location", "jobLocation", "place"),
        "description": first("descriptionText", "description", "jobDescription", "descriptionHtml"),
        "url": first("jobUrl", "link", "url", "jobPostingUrl"),
        "posted_days_ago": 0,  # actors report this inconsistently; freshness left to the API query
        "employment_type": first("contractType", "employmentType", "jobType"),
        "source": "linkedin/apify",
    }


class ApifyFileSource:
    """Rank an Apify dataset you already downloaded (a JSON array of items).

    Lets you run the actor in the Apify console, download the results, and have
    this tool only *rank* them — no token needs to touch this tool.
    """

    name = "apify_file"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self) -> list[dict]:
        if not self.path.exists():
            raise FileNotFoundError(f"Apify dataset file not found: {self.path}")
        items = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(items, dict):                    # some exports wrap items
            items = items.get("items", items.get("data", []))
        return [map_apify_item(it) for it in items]


class ApifySource:
    """Fetch LinkedIn postings via an Apify actor (bring-your-own scraper + token).

    Uses Apify's *run-actor-synchronously-and-get-dataset-items* endpoint, so one
    HTTP call runs the actor and returns the scraped jobs. Set ``APIFY_TOKEN`` and
    an actor id (``JOBSCREENER_APIFY_ACTOR``, e.g. ``misceres~linkedin-jobs-scraper``).

    Note: you rent the actor from Apify (paid) and are responsible for how you use
    scraped data. This project only provides the connector.
    """

    name = "apify"
    ACTOR_ENDPOINT = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
    TASK_ENDPOINT = "https://api.apify.com/v2/actor-tasks/{task}/run-sync-get-dataset-items"

    def __init__(self, token: str | None = None, actor: str | None = None,
                 task: str | None = None, queries: list[str] | None = None,
                 location: str = "", rows: int = 100, input_json: dict | None = None,
                 extra_input: dict | None = None):
        self.token = token or os.environ.get("APIFY_TOKEN")
        self.actor = actor or os.environ.get("JOBSCREENER_APIFY_ACTOR",
                                             "cheap_scraper~linkedin-job-scraper")
        self.task = task or os.environ.get("JOBSCREENER_APIFY_TASK")  # a saved task id
        self.queries = queries or ["credit risk analyst"]
        self.location = location
        self.rows = rows
        self.input_json = input_json       # exact input copied from the actor's JSON tab
        self.extra_input = extra_input or {}

    def _endpoint(self) -> str:
        """Task endpoint if a task id is set, else the actor endpoint."""
        if self.task:
            return self.TASK_ENDPOINT.format(task=self.task)
        return self.ACTOR_ENDPOINT.format(actor=self.actor)

    def _build_input(self) -> dict | None:
        # Verbatim input wins (copied from Apify's JSON tab). For a task with no
        # override we return None -> send an empty body so the task's *saved*
        # input is used. Bare actors get a generic fallback.
        if self.input_json is not None:
            return self.input_json
        if self.task:
            return None
        payload = {"keyword": self.queries, "locations": [self.location] if self.location else [],
                   "maxItems": self.rows}
        payload.update(self.extra_input)
        return payload

    def fetch(self) -> list[dict]:  # pragma: no cover - network + paid API
        if not self.token:
            raise RuntimeError("Set APIFY_TOKEN to use the Apify source.")
        url = self._endpoint() + "?" + urllib.parse.urlencode({"token": self.token})
        payload = self._build_input()
        body = json.dumps(payload if payload is not None else {}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            items = json.loads(resp.read().decode("utf-8"))
        return [map_apify_item(it) for it in items]


class RemotiveSource:
    """Optional live source using Remotive's free, public API (no key, no ToS issue).

    Not used by default so the pipeline stays offline/deterministic; enable it
    explicitly. Network failures raise, so callers can fall back to a file source.
    """

    name = "remotive"
    API = "https://remotive.com/api/remote-jobs"

    def __init__(self, search: str = "analyst", limit: int = 50):
        self.search = search
        self.limit = limit

    def fetch(self) -> list[dict]:  # pragma: no cover - network
        url = f"{self.API}?search={urllib.parse.quote(self.search)}&limit={self.limit}"
        # A browser-like User-Agent avoids the default urllib UA being blocked.
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        out = []
        for j in payload.get("jobs", []):
            out.append({
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", "Remote"),
                "description": j.get("description", ""),
                "url": j.get("url", ""),
                "posted_days_ago": 0,
                "employment_type": j.get("job_type", ""),
                "source": "remotive",
            })
        return out


def map_mcf_item(item: dict, description: str = "") -> dict:
    """Map one MyCareersFuture search result to our raw schema. Pure/testable.

    The search endpoint omits the description, so it's passed in separately (from
    the per-job detail endpoint).
    """
    company = (item.get("postedCompany") or item.get("hiringCompany") or {}).get("name", "")
    meta = item.get("metadata") or {}
    emp = item.get("employmentTypes") or []
    return {
        "title": item.get("title", ""),
        "company": company,
        "location": "Singapore",                      # MyCareersFuture is SG-only
        "description": description,
        "url": meta.get("jobDetailsUrl", ""),
        "posted_days_ago": _days_since(meta.get("newPostingDate")),
        "employment_type": emp[0].get("employmentType", "") if emp else "",
        "source": "mycareersfuture",
    }


class MyCareersFutureSource:
    """Free, official Singapore source: MyCareersFuture (Workforce Singapore).

    A public JSON API — no key, no scraping, no ToS grey-area. Singapore-only.
    The search endpoint doesn't include the job description, so by default we
    fetch each posting's detail page to fill it in (needed for skill scoring).
    Network failures raise so a caller can fall back to another source.
    """

    name = "mycareersfuture"
    SEARCH = "https://api.mycareersfuture.gov.sg/v2/search"
    DETAIL = "https://api.mycareersfuture.gov.sg/v2/jobs/{uuid}"
    _UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

    def __init__(self, search: str = "credit risk analyst", results: int = 30,
                 fetch_descriptions: bool = True):
        self.search = search
        self.results = results
        self.fetch_descriptions = fetch_descriptions

    def _search_page(self, page: int, limit: int) -> list[dict]:
        body = json.dumps({"search": self.search, "sessionId": "jobscreener"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.SEARCH}?limit={limit}&page={page}", data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "User-Agent": self._UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("results", [])

    def _description(self, uuid: str) -> str:
        try:
            req = urllib.request.Request(self.DETAIL.format(uuid=uuid),
                                         headers={"Accept": "application/json", "User-Agent": self._UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8")).get("description", "") or ""
        except (urllib.error.URLError, ValueError, TimeoutError):
            return ""                                   # description is best-effort

    def fetch(self) -> list[dict]:  # pragma: no cover - network
        items: list[dict] = []
        page, limit = 0, min(self.results, 100)
        while len(items) < self.results:
            batch = self._search_page(page, limit)
            if not batch:
                break
            items.extend(batch)
            if len(batch) < limit:
                break
            page += 1
        items = items[: self.results]
        return [map_mcf_item(it, self._description(it["uuid"])
                             if self.fetch_descriptions and it.get("uuid") else "")
                for it in items]
