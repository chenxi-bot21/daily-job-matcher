"""
Soft scoring — rank each posting 0-100 for fit with the CV.

The overall score is a transparent weighted blend of five dimensions, so every
recommendation is explainable (unlike a single opaque number):

  * **skill_match** (40%)  — explicit skill overlap + TF-IDF cosine of CV vs JD text
  * **title_relevance** (25%) — fuzzy match of the job title to target roles
  * **domain_fit** (15%)   — how many target domains the JD touches
  * **seniority_alignment** (10%) — early-career suitability
  * **location_preference** (10%) — preferred locations rank higher

This content-based scorer needs no API key. When one is configured, the LLM
re-scores the shortlist for nuance (see :mod:`jobscreener.llm`).
"""
from __future__ import annotations

from difflib import SequenceMatcher

from sklearn.feature_extraction.text import TfidfVectorizer

from .config import Settings
from .cv import CVProfile, skill_present
from .models import JobPosting, ScoreBreakdown, ScoredJob

_SENIORITY_SCORE = {"entry": 100.0, "internship": 90.0, "mid": 60.0, "senior": 0.0}


def _best_title_ratio(title: str, roles: list[str]) -> float:
    title = title.lower()
    best = max((SequenceMatcher(None, title, r).ratio() for r in roles), default=0.0)
    if any(r in title for r in roles):          # exact substring is a strong signal
        best = max(best, 0.85)
    return best * 100.0


class HeuristicScorer:
    """Deterministic, offline content-based scorer."""

    def __init__(self, settings: Settings, cv: CVProfile):
        self.settings = settings
        self.cv = cv
        self.cv_skills = set(cv.skills)

    def score_all(self, jobs: list[JobPosting]) -> list[ScoredJob]:
        if not jobs:
            return []
        # Fit TF-IDF once over the CV + all JDs for a shared vocabulary.
        corpus = [self.cv.text] + [j.text() for j in jobs]
        matrix = TfidfVectorizer(stop_words="english", max_features=5000).fit_transform(corpus)
        cv_vec, job_vecs = matrix[0], matrix[1:]
        cosine = (job_vecs @ cv_vec.T).toarray().ravel()  # l2-normalised -> cosine
        return [self._score_one(job, float(cosine[i])) for i, job in enumerate(jobs)]

    def _score_one(self, job: JobPosting, cosine: float) -> ScoredJob:
        p, w = self.settings.profile, self.settings.weights
        blob = job.text().lower()

        # --- skill match ---
        jd_skills = {s for s in p.skills if skill_present(blob, s)}
        matched = sorted(self.cv_skills & jd_skills)
        overlap = len(matched) / max(len(jd_skills), 1)
        skill = 100.0 * (0.6 * overlap + 0.4 * cosine)

        # --- title / domain / seniority / location ---
        title = _best_title_ratio(job.title, p.target_roles)
        domains_hit = sum(1 for d in p.target_domains if d in blob)
        domain = min(domains_hit / 2.0, 1.0) * 100.0
        seniority = _SENIORITY_SCORE.get(job.seniority, 50.0)
        loc = job.location.lower()
        if any(pl in loc for pl in p.preferred_locations):
            location = 100.0
        elif "remote" in loc or not loc:
            location = 90.0
        else:
            location = 50.0

        breakdown = ScoreBreakdown(skill, title, domain, seniority, location)
        overall = (w.skill_match * skill + w.title_relevance * title + w.domain_fit * domain
                   + w.seniority_alignment * seniority + w.location_preference * location)

        return ScoredJob(
            job=job, score=round(overall, 1), breakdown=breakdown,
            matched_skills=matched, reasons=self._reasons(job, matched, title, location),
        )

    def _reasons(self, job, matched, title_score, location_score) -> list[str]:
        reasons = []
        if matched:
            reasons.append("Matches your skills: " + ", ".join(matched[:6]))
        if title_score >= 80:
            reasons.append(f"Title fits a target role ({job.title})")
        if location_score >= 100:
            reasons.append(f"Preferred location: {job.location}")
        elif location_score >= 90:
            reasons.append("Remote-friendly")
        if job.seniority in ("entry", "internship"):
            reasons.append("Early-career level suits you")
        return reasons
