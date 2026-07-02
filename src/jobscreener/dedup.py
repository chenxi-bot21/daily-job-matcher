"""De-duplicate near-identical postings (part of *Filter and deduplicate*)."""
from __future__ import annotations

from difflib import SequenceMatcher

from .models import JobPosting

_COMPANY_THRESHOLD = 0.90
_TITLE_THRESHOLD = 0.85


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_duplicate(a: JobPosting, b: JobPosting) -> bool:
    if a.url and a.url == b.url:
        return True
    # Same job re-posted: the *company* must match closely, not just the title
    # (otherwise "Old Bank / Analyst" and "Mox Bank / Analyst" wrongly merge).
    return _ratio(a.company, b.company) >= _COMPANY_THRESHOLD and \
        _ratio(a.title, b.title) >= _TITLE_THRESHOLD


def deduplicate(jobs: list[JobPosting]) -> list[JobPosting]:
    """Keep one posting per (company, title); on a tie keep the freshest."""
    kept: list[JobPosting] = []
    for job in sorted(jobs, key=lambda j: j.posted_days_ago):  # freshest first
        if not any(_is_duplicate(job, k) for k in kept):
            kept.append(job)
    return kept
