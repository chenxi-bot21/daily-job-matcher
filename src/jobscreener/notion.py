"""
Push the daily shortlist to a Notion database (the *Output & Notification* step).

Disabled unless ``NOTION_TOKEN`` and ``NOTION_DATABASE_ID`` are set, so nothing
is written by accident. The writer introspects the database schema and fills
whatever columns exist (matched case-insensitively), so it adapts to your table
rather than forcing an exact layout. Recommended columns:

    Name (title) · Company · Location · Score (number) · Status (select) ·
    Skills · URL (url) · Date (date) · Source

Setup: create an integration at https://www.notion.so/my-integrations, copy its
token, create a database, share it with the integration, and copy the database
id from its URL.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import date

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


def notion_configured() -> bool:
    return bool(os.environ.get("NOTION_TOKEN") and os.environ.get("NOTION_DATABASE_ID"))


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }


def _request(method: str, url: str, payload: dict | None = None) -> dict:  # pragma: no cover - network
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _value_for_type(prop_type: str, value) -> dict:
    """Wrap *value* in the shape Notion expects for a given property type."""
    text = "" if value is None else str(value)
    if prop_type == "title":
        return {"title": [{"text": {"content": text[:2000]}}]}
    if prop_type == "rich_text":
        return {"rich_text": [{"text": {"content": text[:1900]}}]}
    if prop_type == "number":
        try:
            return {"number": float(value)}
        except (TypeError, ValueError):
            return {"number": None}
    if prop_type == "select":
        return {"select": {"name": text[:100]} if text else None}
    if prop_type == "multi_select":
        items = value if isinstance(value, list) else [s.strip() for s in text.split(",") if s.strip()]
        return {"multi_select": [{"name": str(s)[:100]} for s in items[:10]]}
    if prop_type == "url":
        return {"url": text or None}
    if prop_type == "date":
        return {"date": {"start": text} if text else None}
    return {"rich_text": [{"text": {"content": text[:1900]}}]}


def build_properties(scored, meta: dict, schema: dict) -> dict:
    """Build Notion page properties for *scored*, filling only columns that exist.

    *schema* maps property name -> Notion type. Pure and unit-testable.
    """
    by_lower = {name.lower(): name for name in schema}
    props: dict = {}

    def put(value, *candidate_names):
        for cand in candidate_names:
            name = by_lower.get(cand.lower())
            if name:
                props[name] = _value_for_type(schema[name], value)
                return

    job = scored.job
    title_name = next((n for n, t in schema.items() if t == "title"), None)
    if title_name:
        props[title_name] = _value_for_type("title", job.title)

    put(job.company, "Company", "Employer")
    put(job.location, "Location")
    put(round(scored.score, 1), "Score", "Match", "Fit")
    put("To Apply", "Status")
    put(", ".join(scored.matched_skills[:8]) or "—", "Skills", "Matched Skills")
    put(job.url, "URL", "Link", "Job URL")
    put(date.today().isoformat(), "Date", "Date Found")
    put(job.source or meta.get("source", ""), "Source")
    return props


def push_jobs(scored_jobs, meta: dict) -> int:  # pragma: no cover - network
    """Create one Notion page per job; returns the number successfully written."""
    if not notion_configured():
        raise RuntimeError("Set NOTION_TOKEN and NOTION_DATABASE_ID to push to Notion.")
    db_id = os.environ["NOTION_DATABASE_ID"]
    schema = _request("GET", f"{API}/databases/{db_id}").get("properties", {})
    schema = {name: meta_.get("type", "rich_text") for name, meta_ in schema.items()}

    written = 0
    for scored in scored_jobs:
        payload = {"parent": {"database_id": db_id},
                   "properties": build_properties(scored, meta, schema)}
        try:
            _request("POST", f"{API}/pages", payload)
            written += 1
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"  Notion write failed for '{scored.job.title[:40]}': {exc}")
    return written
