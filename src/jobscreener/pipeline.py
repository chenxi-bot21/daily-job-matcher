"""
End-to-end orchestration — the full workflow from the architecture diagram.

    CV → jobs → normalise → dedup → hard-filter → heuristic score → (LLM shortlist
    re-score) → rank → top-N → HTML report.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import filters, history
from .config import Settings
from .cv import load_cv
from .dedup import deduplicate
from .models import ScoredJob
from .normalize import normalize_all
from .scoring import HeuristicScorer
from .sources import JobSource, SampleFileSource


@dataclass
class ScreeningResult:
    top: list[ScoredJob]                 # the top-N shortlist for the report
    all_scored: list[ScoredJob]          # every job that passed filters, ranked
    meta: dict = field(default_factory=dict)


def run_screening(settings: Settings, source: JobSource | None = None,
                  exclude_seen: bool = False) -> ScreeningResult:
    # 1-3. CV: retrieve → extract → map to a skill profile.
    cv = load_cv(settings.cv_path, settings.profile.skills)

    # 4. Ingest raw postings.
    source = source or SampleFileSource(settings.jobs_path)
    raws = source.fetch()

    # 5. Normalise, then 6. de-duplicate (within this run).
    jobs = deduplicate(normalize_all(raws))

    # 6b. Cross-run de-dup: drop jobs already surfaced in earlier runs.
    n_seen_skipped = 0
    if exclude_seen:
        seen = history.load_seen(settings.seen_path)
        before = len(jobs)
        jobs = [j for j in jobs if j.id not in seen]
        n_seen_skipped = before - len(jobs)

    # 7. Hard filters (knock-out gate).
    kept, dropped = filters.apply_filters(jobs, settings)

    # 8. Heuristic scoring + initial ranking.
    scored = HeuristicScorer(settings, cv).score_all(kept)
    scored.sort(key=lambda s: s.score, reverse=True)

    # 9. Optional LLM re-scoring of the shortlist (bounded token cost).
    llm_used = False
    if settings.use_llm and settings.api_key:
        from .llm import rescore_with_llm
        shortlist = scored[: max(settings.top_n + 5, 20)]
        rescore_with_llm(shortlist, cv, settings)
        scored.sort(key=lambda s: s.score, reverse=True)  # shortlist objects mutated in place
        llm_used = True

    # 10. Select top-N above the score floor.
    top = [s for s in scored if s.score >= settings.min_score][: settings.top_n]

    # Remember what we surfaced so future runs don't repeat it.
    if exclude_seen:
        history.record_seen(settings.seen_path, [s.job.id for s in top])

    meta = {
        "n_fetched": len(raws),
        "n_after_dedup": len(jobs),
        "n_seen_skipped": n_seen_skipped,
        "n_after_filter": len(kept),
        "dropped": dict(dropped),
        "llm_used": llm_used,
        "cv_skills": cv.skills,
        "source": source.name,
    }
    return ScreeningResult(top=top, all_scored=scored, meta=meta)
