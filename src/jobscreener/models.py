"""Core data structures shared across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobPosting:
    """A normalised job posting."""

    id: str
    title: str
    company: str
    location: str
    description: str
    url: str = ""
    posted_days_ago: int = 0
    seniority: str = ""          # e.g. "entry", "mid", "senior"
    employment_type: str = ""    # e.g. "full_time", "internship"
    source: str = ""

    def text(self) -> str:
        """Concatenated text used for matching."""
        return f"{self.title} {self.company} {self.description}"


@dataclass
class ScoreBreakdown:
    """Per-dimension contributions to the overall fit score (all 0-100)."""

    skill_match: float = 0.0
    title_relevance: float = 0.0
    domain_fit: float = 0.0
    seniority_alignment: float = 0.0
    location_preference: float = 0.0

    def as_dict(self) -> dict:
        return {
            "skill_match": round(self.skill_match, 1),
            "title_relevance": round(self.title_relevance, 1),
            "domain_fit": round(self.domain_fit, 1),
            "seniority_alignment": round(self.seniority_alignment, 1),
            "location_preference": round(self.location_preference, 1),
        }


@dataclass
class ScoredJob:
    """A posting plus its fit score and human-readable rationale."""

    job: JobPosting
    score: float                              # overall 0-100
    breakdown: ScoreBreakdown
    matched_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    llm_used: bool = False
