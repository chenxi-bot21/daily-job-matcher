"""
Configuration: candidate profile, screening rules, scoring weights, and paths.

Secrets (API key, SMTP password) come from the environment / a git-ignored
``.env``; everything else has sensible defaults tuned to the candidate profile.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent  # D:\download\RESUME


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class CandidateProfile:
    """What the candidate wants — drives both hard filters and soft scoring."""

    target_roles: list[str] = field(default_factory=lambda: [
        "credit risk analyst", "credit risk", "risk analyst", "credit analyst",
        "model validation", "model risk", "fixed income analyst", "credit research",
        "quantitative research analyst", "quantitative analyst", "research analyst",
        "data analyst", "data scientist", "biostatistician", "statistical programmer",
        "graduate analyst", "analyst programme",
    ])
    target_domains: list[str] = field(default_factory=lambda: [
        "credit risk", "risk management", "fixed income", "credit", "model validation",
        "quantitative research", "data analytics", "biostatistics", "real-world evidence",
        "statistics", "market risk",
    ])
    # Scarce, high-value roles to push the candidate TOWARD: quantitative /
    # modelling / model-validation / risk-data-science work. Local talent is thin
    # here, so employers are likelier to sponsor a strong new grad — the opposite
    # of generic analyst/KYC roles (see ScreeningRules.deprioritize_title_keywords).
    # Matched against the job TITLE; a hit adds a score boost.
    priority_title_keywords: list[str] = field(default_factory=lambda: [
        "model validation", "model risk", "credit risk model", "risk model",
        "modelling", "modeling", "scorecard", "quant", "quantitative",
        "data scientist", "data science", "ifrs 9", "market risk", "risk analytics",
    ])
    # Skill taxonomy the candidate possesses (lower-case, matched as substrings).
    skills: list[str] = field(default_factory=lambda: [
        "python", "r", "sql", "vba", "sas", "stata", "tableau", "excel",
        "pandas", "numpy", "scikit-learn", "xgboost", "machine learning",
        "logistic regression", "scorecard", "woe", "credit risk", "ifrs 9",
        "pd", "lgd", "ead", "var", "value at risk", "expected shortfall",
        "fixed income", "duration", "yield", "z-spread", "derivatives",
        "survival analysis", "propensity score", "regression", "time series",
        "biostatistics", "clinical", "epidemiology", "financial econometrics",
    ])
    # US removed 2026-07 — the user is no longer searching there.
    preferred_locations: list[str] = field(default_factory=lambda: [
        "hong kong", "singapore", "china", "beijing", "shanghai", "shenzhen",
        "remote",
    ])
    max_experience_years: int = 3          # entry / early-career
    accept_internships: bool = True

    # --- Hard constraints (knock-outs), standard ATS-style gating ---
    # New graduate with ~1 year of internships (no full-time). A JD's stated
    # MINIMUM required years must be <= this to keep the role; more is knocked out.
    # =2 keeps "0-2 years / entry / no experience" and mild "2-5 yr" stretches,
    # but knocks out "minimum 3 years" and up (which a new grad does not meet).
    max_years_experience: int = 2
    highest_degree: str = "master"         # bachelor | master | phd
    needs_visa_sponsorship: bool = True    # foreign national -> citizenship-only roles knock out


@dataclass
class ScreeningRules:
    """Hard filters applied before scoring."""

    freshness_days: int = 21
    exclude_keywords: list[str] = field(default_factory=lambda: [
        "php", "wordpress", "nurse", "warehouse", "driver", "chef",
        "director", "head of", "vice president", "vp,", "principal",
    ])
    # Title tokens that mark a role as a poor fit (trading desks, HFT, sales,
    # senior). Checked against the TITLE only, so a risk role whose description
    # merely mentions "trading" is not dropped.
    exclude_title_keywords: list[str] = field(default_factory=lambda: [
        "trader", "trading", "high frequency", "high-frequency", "hft",
        "delta one", "market maker", "market making", "sales", "software engineer",
    ])
    # Seniority tokens that disqualify a role for an early-career candidate.
    senior_tokens: list[str] = field(default_factory=lambda: [
        "senior", "lead ", "principal", "staff ", "head of", "director",
        "vice president", "manager,", "10+ years", "8+ years", "7+ years",
    ])
    # Generic / low-fit titles to push DOWN (a penalty, not a knock-out). These
    # rank below the scarce modelling/quant roles in priority_title_keywords.
    # Matched against the TITLE. NOTE (2026-07-04): AML/KYC/compliance were REMOVED
    # from this list — they are a genuine, winnable target track for this candidate
    # (she applies to and gets responses from them), so the pipeline no longer
    # both searches for and penalises them.
    deprioritize_title_keywords: list[str] = field(default_factory=lambda: [
        "accounts receivable", "credit control", "collections", "underwriter",
        "underwriting", "audit", "business analyst", "administrator", "clerk",
    ])


@dataclass
class ScoringWeights:
    """Weights for the soft-score blend (should sum to 1.0)."""

    skill_match: float = 0.40
    title_relevance: float = 0.25
    domain_fit: float = 0.15
    seniority_alignment: float = 0.10
    location_preference: float = 0.10


@dataclass
class Settings:
    profile: CandidateProfile = field(default_factory=CandidateProfile)
    rules: ScreeningRules = field(default_factory=ScreeningRules)
    weights: ScoringWeights = field(default_factory=ScoringWeights)

    top_n: int = 15
    min_score: float = 40.0                # drop jobs below this from the report

    # Paths
    cv_path: Path = field(default_factory=lambda: _env_path(
        "JOBSCREENER_CV", WORKSPACE_ROOT / "career" / "PROFILE.md"))
    jobs_path: Path = field(default_factory=lambda: _env_path(
        "JOBSCREENER_JOBS", PROJECT_ROOT / "data" / "sample_jobs.json"))
    output_dir: Path = field(default_factory=lambda: _env_path(
        "JOBSCREENER_OUTPUT", PROJECT_ROOT / "output"))

    # LLM
    model: str = field(default_factory=lambda: os.environ.get("JOBSCREENER_MODEL", "claude-sonnet-5"))
    use_llm: bool = field(default_factory=lambda: bool(os.environ.get("ANTHROPIC_API_KEY")))

    @property
    def api_key(self) -> str | None:
        return os.environ.get("ANTHROPIC_API_KEY")

    @property
    def seen_path(self) -> Path:
        """Where previously-surfaced job ids are logged (for cross-run dedup)."""
        return self.output_dir / "seen_jobs.json"


def _env_path(name: str, default: Path) -> Path:
    v = os.environ.get(name)
    return Path(v).expanduser() if v else default


def get_settings() -> Settings:
    return Settings()
