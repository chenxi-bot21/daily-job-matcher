"""
Hard filters — cheap, deterministic rules that drop obvious non-fits *before*
the (token-costly) scoring step. Mirrors the workflow's keyword filtering.

Kept intentionally conservative: hard filters should only remove clear
non-matches; borderline relevance is left to the soft scorer, which ranks
rather than excludes.
"""
from __future__ import annotations

import re
from collections import Counter

from .config import Settings
from .models import JobPosting

# --- Knock-out phrase lists (hard eligibility disqualifiers) ---------------
# Citizenship / no-sponsorship phrases that exclude a foreign national needing
# visa sponsorship. Kept specific to avoid false hits on "based in Singapore".
_ELIGIBILITY_KNOCKOUTS = [
    "only singaporeans", "singaporeans only", "singaporeans need apply",
    "singaporean citizens", "singapore citizens only", "singapore citizen only",
    "must be a singapore citizen", "citizens only", "citizens and pr",
    "citizens & pr", "sc/pr only", "sc / pr only", "pr only",
    "permanent residents only", "must be a citizen", "citizenship required",
    "no visa sponsorship", "not provide sponsorship", "without sponsorship",
    "will not sponsor", "do not sponsor", "unable to sponsor",
    "security clearance", "right of abode", "permanent resident of hong kong",
]
# PhD-required signals; softeners below cancel them.
_PHD_REQUIRED = [
    "phd required", "ph.d. required", "phd is required", "requires a phd",
    "must have a phd", "doctorate required", "doctoral degree required",
    "postdoctoral", "post-doctoral", "postdoc",
]
_PHD_SOFTENERS = ["phd or equivalent", "ph.d. or equivalent", "phd preferred",
                  "phd is a plus", "phd/master", "master or phd", "phd or master's"]

_YEARS_PATTERNS = [
    r"(\d+)\s*\+?\s*(?:to|-|–|—)\s*\d+\s*years",                 # "2-5 years" -> 2
    r"(?:minimum|min\.?|at least)\s*(?:of\s*)?(\d+)\s*\+?\s*years",
    r"(\d+)\s*\+\s*years",                                       # "5+ years"
    r"(\d+)\s*years?\s*(?:or above|or more)",                    # "2 years or above"
    # "3 years of relevant work experience" (allow stacked adjectives); the
    # experience keyword prevents matching company ages like "over 180 years".
    r"(\d+)\s*years?\s+(?:of\s+)?(?:(?:relevant|related|professional|work|industry)\s+){0,3}experience",
]


def passes_freshness(job: JobPosting, settings: Settings) -> bool:
    return job.posted_days_ago <= settings.rules.freshness_days


_REMOTE_TOKENS = ("remote", "anywhere", "worldwide", "global")


def passes_location(job: JobPosting, settings: Settings) -> bool:
    loc = job.location.lower()
    if not loc or any(t in loc for t in _REMOTE_TOKENS):
        return True
    return any(p in loc for p in settings.profile.preferred_locations)


def passes_seniority(job: JobPosting, settings: Settings) -> bool:
    if job.seniority == "senior":
        return False
    if job.seniority == "internship" and not settings.profile.accept_internships:
        return False
    blob = f"{job.title} {job.description}".lower()
    return not any(tok in blob for tok in settings.rules.senior_tokens)


def passes_keywords(job: JobPosting, settings: Settings) -> bool:
    blob = f"{job.title} {job.description}".lower()
    return not any(kw in blob for kw in settings.rules.exclude_keywords)


def passes_title(job: JobPosting, settings: Settings) -> bool:
    """Drop trading/HFT/sales roles by title (a poor fit for this candidate)."""
    title = job.title.lower()
    return not any(kw in title for kw in settings.rules.exclude_title_keywords)


# ---------------------------------------------------------------------------
# Knock-outs — hard, non-negotiable disqualifiers (ATS-style "knockout gate")
# ---------------------------------------------------------------------------
def min_years_required(text: str) -> int | None:
    """Smallest years-of-experience requirement stated in the JD, or None.

    Only matches years tied to an experience/requirement context, so company
    ages ("for over 180 years") are ignored. Returns the minimum across matches
    (least aggressive) to avoid false knock-outs.
    """
    years = []
    for pat in _YEARS_PATTERNS:
        years += [int(m) for m in re.findall(pat, text, flags=re.IGNORECASE)]
    return min(years) if years else None


def passes_experience(job: JobPosting, settings: Settings) -> bool:
    """Knock out roles requiring more years than the candidate can offer.

    Keep when required_years <= max_years_experience (default 3); knock out more.
    """
    required = min_years_required(f"{job.title} {job.description}")
    if required is None:
        return True
    return required <= settings.profile.max_years_experience


def passes_eligibility(job: JobPosting, settings: Settings) -> bool:
    """Knock out citizenship-only / no-sponsorship roles for a candidate who
    needs visa sponsorship."""
    if not settings.profile.needs_visa_sponsorship:
        return True
    blob = f"{job.title} {job.description}".lower()
    return not any(p in blob for p in _ELIGIBILITY_KNOCKOUTS)


def passes_degree(job: JobPosting, settings: Settings) -> bool:
    """Knock out PhD/postdoc-required roles when the candidate is below that."""
    if settings.profile.highest_degree == "phd":
        return True
    blob = f"{job.title} {job.description}".lower()
    if any(s in blob for s in _PHD_SOFTENERS):
        return True
    return not any(p in blob for p in _PHD_REQUIRED)


def passes_relevance(job: JobPosting, settings: Settings) -> bool:
    """Require at least one target role/domain/skill token — drops off-domain roles."""
    blob = f"{job.title} {job.description}".lower()
    tokens = settings.profile.target_roles + settings.profile.target_domains + settings.profile.skills
    return any(t in blob for t in tokens)


_CHECKS = {
    # Hard knock-outs (non-negotiable) first.
    "not_eligible": passes_eligibility,       # visa / citizenship / clearance
    "over_experienced": passes_experience,    # JD requires far more years
    "needs_phd": passes_degree,               # PhD / postdoc required
    # Fit-based hard filters.
    "stale": passes_freshness,
    "location": passes_location,
    "seniority": passes_seniority,
    "excluded_keyword": passes_keywords,
    "wrong_role_type": passes_title,
    "off_domain": passes_relevance,
}


def apply_filters(jobs: list[JobPosting], settings: Settings) -> tuple[list[JobPosting], Counter]:
    """Return (kept jobs, Counter of drop reasons)."""
    kept: list[JobPosting] = []
    dropped: Counter = Counter()
    for job in jobs:
        reason = next((name for name, check in _CHECKS.items() if not check(job, settings)), None)
        if reason:
            dropped[reason] += 1
        else:
            kept.append(job)
    return kept, dropped
