"""Combine LinkedIn + Indeed + MyCareersFuture into one ranked curation file.

Runs on the screener's Python 3.14. Screens each source pool through the same
knock-out gate + heuristic score, merges them, de-dups by company+title (keeping
the highest score), and writes ``output/combined_full.json`` — every passing
candidate with its full JD, source, apply URL and score, ready to hand-curate.

Inputs (all optional; skip a source by omitting its file / flag):
  --apify   output/apify_raw.json   LinkedIn (from `run --source apify ...`)
  --indeed  output/indeed_24h.csv   Indeed   (from scripts/fetch_indeed.py)
  --mcf-terms "a,b,c"               MyCareersFuture live search terms
  --mcf-max-age 1                   keep only MCF postings <= N days old (24h = 1)

Usage:
    python scripts/combine_sources.py
Then read output/combined_full.json and hand-curate (see docs/DAILY_PLAYBOOK.md).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from jobscreener.config import get_settings
from jobscreener import dedup, filters, history, scoring
from jobscreener.cv import load_cv
from jobscreener.normalize import normalize_all
from jobscreener.sources import ApifyFileSource, JobSpyCsvSource, MyCareersFutureSource

DEFAULT_MCF_TERMS = ["credit risk analyst", "risk analyst", "credit analyst",
                     "data analyst", "quantitative analyst"]


def _label(src: str) -> str:
    src = (src or "").lower()
    if "linkedin" in src:
        return "LinkedIn"
    if "indeed" in src or "jobspy" in src:
        return "Indeed"
    if "mycareers" in src:
        return "MyCareersFuture"
    return src or "?"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Merge job sources into one ranked curation file.")
    p.add_argument("--apify", default="output/apify_raw.json", help="LinkedIn raw dataset JSON")
    p.add_argument("--indeed", default="output/indeed_24h.csv", help="Indeed CSV from the sidecar")
    p.add_argument("--mcf-terms", default=",".join(DEFAULT_MCF_TERMS), help="MCF search terms")
    p.add_argument("--mcf-max-age", type=int, default=1, help="keep MCF postings <= N days old")
    p.add_argument("--out", default="output/combined_full.json")
    args = p.parse_args(argv)

    s = get_settings()
    cv = load_cv(s.cv_path, s.profile.skills)

    def screen(raws):
        jobs = dedup.deduplicate(normalize_all(raws))
        kept, dropped = filters.apply_filters(jobs, s)
        return scoring.HeuristicScorer(s, cv).score_all(kept), dict(dropped), len(jobs)

    pool = []

    if Path(args.apify).exists():
        raws = ApifyFileSource(args.apify).fetch()
        sc, dr, n = screen(raws); pool += sc
        print(f"LinkedIn : {len(raws)} raw -> {n} dedup -> {len(sc)} passed  {dr}")
    else:
        print(f"LinkedIn : (skipped — {args.apify} not found)")

    if Path(args.indeed).exists():
        raws = JobSpyCsvSource(args.indeed).fetch()
        sc, dr, n = screen(raws); pool += sc
        print(f"Indeed   : {len(raws)} raw -> {n} dedup -> {len(sc)} passed  {dr}")
    else:
        print(f"Indeed   : (skipped — {args.indeed} not found)")

    mcf_raw, seen = [], set()
    for term in [t.strip() for t in args.mcf_terms.split(",") if t.strip()]:
        try:
            for r in MyCareersFutureSource(search=term, results=40, fetch_descriptions=True).fetch():
                if r["url"] not in seen:
                    seen.add(r["url"]); mcf_raw.append(r)
        except Exception as e:
            print("  MCF err", term, type(e).__name__, str(e)[:50])
    mcf_fresh = [r for r in mcf_raw if r.get("posted_days_ago", 99) <= args.mcf_max_age]
    sc, dr, n = screen(mcf_fresh); pool += sc
    print(f"MCF      : {len(mcf_raw)} fetched -> {len(mcf_fresh)} within {args.mcf_max_age}d "
          f"-> {n} dedup -> {len(sc)} passed  {dr}")

    # merge across sources; keep the highest-scoring copy of each company+title.
    best = {}
    for sj in pool:
        k = history.content_key(sj.job.company, sj.job.title)
        if k not in best or sj.score > best[k].score:
            best[k] = sj
    merged = sorted(best.values(), key=lambda x: x.score, reverse=True)

    out = [{
        "score": round(sj.score, 1), "source": _label(sj.job.source),
        "title": sj.job.title, "company": sj.job.company, "location": sj.job.location,
        "seniority": sj.job.seniority, "posted_days_ago": sj.job.posted_days_ago,
        "url": sj.job.url, "matched": sj.matched_skills, "description": sj.job.description,
    } for sj in merged]
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nMERGED: {len(out)} unique -> {args.out}   by source: {dict(Counter(r['source'] for r in out))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
