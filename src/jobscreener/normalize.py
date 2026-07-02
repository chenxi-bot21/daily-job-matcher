"""Standardise raw postings into :class:`JobPosting` objects (the *NormalizeData* step)."""
from __future__ import annotations

import hashlib
import re

from .models import JobPosting

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_INTERN_TOKENS = ("intern", "internship", "trainee", "co-op")
_ENTRY_TOKENS = ("graduate", "entry", "junior", "associate", "analyst", "new grad")
_SENIOR_TOKENS = ("senior", "lead", "principal", "staff", "head of", "director",
                  "vice president", "vp ", "manager")


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", text or "")).strip()


def _make_id(raw: dict) -> str:
    if raw.get("id"):
        return str(raw["id"])
    key = f"{raw.get('company','')}|{raw.get('title','')}|{raw.get('url','')}".lower()
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def infer_seniority(title: str, description: str) -> str:
    blob = f"{title} {description}".lower()
    if any(t in blob for t in _INTERN_TOKENS):
        return "internship"
    if any(t in title.lower() for t in _SENIOR_TOKENS):
        return "senior"
    if any(t in blob for t in _ENTRY_TOKENS):
        return "entry"
    return "mid"


def normalize(raw: dict) -> JobPosting:
    title = _clean(raw.get("title", ""))
    description = _clean(raw.get("description", ""))
    return JobPosting(
        id=_make_id(raw),
        title=title,
        company=_clean(raw.get("company", "")),
        location=_clean(raw.get("location", "")),
        description=description,
        url=raw.get("url", ""),
        posted_days_ago=int(raw.get("posted_days_ago", 0) or 0),
        seniority=raw.get("seniority") or infer_seniority(title, description),
        employment_type=raw.get("employment_type", ""),
        source=raw.get("source", ""),
    )


def normalize_all(raws: list[dict]) -> list[JobPosting]:
    return [normalize(r) for r in raws]
