"""Command line: ``python -m jobscreener run``."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .config import get_settings
from .pipeline import run_screening
from .report import build_html, write_report
import os

from .sources import (ApifyFileSource, ApifySource, JobSpyCsvSource, JobSpySource,
                      RemotiveSource, SampleFileSource)


def _cmd_run(args) -> int:
    settings = get_settings()
    if args.cv:
        settings.cv_path = Path(args.cv)
    if args.jobs:
        settings.jobs_path = Path(args.jobs)
    if args.top:
        settings.top_n = args.top

    source = None
    if args.source == "remotive":
        source = RemotiveSource(search=args.search or "analyst")
    elif args.source == "apify":
        input_json = None
        input_path = args.apify_input or os.environ.get("JOBSCREENER_APIFY_INPUT")
        if input_path:
            input_json = json.loads(Path(input_path).read_text(encoding="utf-8"))
        queries = [args.search] if args.search else settings.profile.target_roles[:5]
        source = ApifySource(queries=queries, location=args.location or "", input_json=input_json)
    elif args.source == "jobspy":
        proxies = None
        raw_proxies = args.proxies or os.environ.get("JOBSCREENER_PROXIES", "")
        if raw_proxies:
            proxies = [p.strip() for p in raw_proxies.split(",") if p.strip()]
        source = JobSpySource(
            search=args.search or settings.profile.target_roles[0],
            location=args.location or "",
            sites=[s.strip() for s in args.sites.split(",")] if args.sites else None,
            country=args.country or "usa",
            results=args.results or 80,
            hours_old=settings.rules.freshness_days * 24,
            proxies=proxies,
        )
    elif args.source == "apify-file":
        source = ApifyFileSource(settings.jobs_path)          # a downloaded Apify dataset JSON
    elif args.jobs:
        if str(settings.jobs_path).lower().endswith(".csv"):
            source = JobSpyCsvSource(settings.jobs_path)      # a CSV JobSpy produced
        else:
            source = SampleFileSource(settings.jobs_path)

    result = run_screening(settings, source=source, exclude_seen=args.exclude_seen)

    # Console summary.
    m = result.meta
    seen_note = f" (−{m['n_seen_skipped']} already seen)" if m.get("n_seen_skipped") else ""
    print(f"\nFetched {m['n_fetched']} → {m['n_after_dedup']} after dedup{seen_note} → "
          f"{m['n_after_filter']} passed filters → top {len(result.top)} shown")
    if m["dropped"]:
        print("Dropped:", ", ".join(f"{k}={v}" for k, v in m["dropped"].items()))
    print(f"Scoring: {'AI + heuristic' if m['llm_used'] else 'heuristic (no API key)'}\n")
    for i, s in enumerate(result.top, 1):
        print(f"{i:>2}. {s.score:>5.1f}  {s.job.title[:48]:<48}  {s.job.company[:22]:<22} {s.job.location[:16]}")

    # HTML report.
    html = build_html(result.top, result.meta)
    out = write_report(html, settings.output_dir / f"job_matches_{date.today().isoformat()}.html")
    print(f"\nReport: {out}")

    # Machine-readable shortlist (for pushing to Notion / other tools).
    top_json = [{
        "date": date.today().isoformat(), "title": s.job.title, "company": s.job.company,
        "location": s.job.location, "score": s.score, "seniority": s.job.seniority,
        "skills": s.matched_skills, "url": s.job.url, "source": s.job.source,
    } for s in result.top]
    json_path = settings.output_dir / "top_jobs.json"
    json_path.write_text(json.dumps(top_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON:   {json_path}")

    # Full curation dump — EVERY candidate that passed the knock-out gate, with
    # its full job description, score and reasons. This is what a human (or
    # another session) reads to hand-curate true fit; the top-N above is only a
    # first pass. Written on every run so the JDs are never lost.
    full = [{
        "score": round(s.score, 1), "title": s.job.title, "company": s.job.company,
        "location": s.job.location, "seniority": s.job.seniority, "url": s.job.url,
        "matched": s.matched_skills, "reasons": s.reasons,
        "description": s.job.description,
    } for s in result.all_scored]
    full_path = settings.output_dir / "candidates_full.json"
    full_path.write_text(json.dumps(full, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Full:   {full_path}  ({len(full)} candidates with JDs)")

    # For live sources, also persist the raw fetched postings so the exact run
    # can be re-screened offline without re-scraping (and re-paying):
    #   python -m jobscreener run --source sample --jobs output/fetched.json
    if args.source in ("apify", "remotive", "jobspy") and result.raws:
        fetched_path = settings.output_dir / "fetched.json"
        fetched_path.write_text(json.dumps(result.raws, ensure_ascii=False), encoding="utf-8")
        print(f"Raw:    {fetched_path}  ({len(result.raws)} fetched)")

    # Push to Notion when configured (or forced with --notion).
    from . import notion
    if notion.notion_configured() and not args.no_notion:
        written = notion.push_jobs(result.top, result.meta)
        print(f"Notion: wrote {written} job(s) to your database.")
    elif args.notion:
        print("ERROR: --notion set but NOTION_TOKEN / NOTION_DATABASE_ID are missing.", file=sys.stderr)

    if args.email:
        from .email_out import send_report
        send_report(html, subject=f"Your job matches — {date.today().isoformat()}")
        print("Email sent.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobscreener",
                                description="Daily AI job-screening pipeline.")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="screen jobs and build the report")
    r.add_argument("--cv", help="path to your CV (.md/.txt/.docx/.pdf)")
    r.add_argument("--jobs", help="path to a postings JSON file")
    r.add_argument("--source", choices=["sample", "remotive", "apify", "apify-file", "jobspy"],
                   default="sample", help="job source (default: bundled sample file)")
    r.add_argument("--search", help="search term for the remotive/apify/jobspy source")
    r.add_argument("--location", help="location filter, e.g. 'Hong Kong'")
    r.add_argument("--sites", help="jobspy: comma list, e.g. 'linkedin,indeed,glassdoor'")
    r.add_argument("--country", help="jobspy: country for Indeed/Glassdoor, e.g. 'Hong Kong'")
    r.add_argument("--results", type=int, help="jobspy: postings to fetch per site")
    r.add_argument("--proxies", help="jobspy: comma-separated proxies (host:port or user:pass@host:port)")
    r.add_argument("--apify-input", help="apify: path to a JSON file with the actor's input (from its JSON tab)")
    r.add_argument("--top", type=int, help="number of matches to show")
    r.add_argument("--email", action="store_true", help="also email the report (needs SMTP env)")
    r.add_argument("--notion", action="store_true", help="require pushing to Notion (else auto if configured)")
    r.add_argument("--no-notion", action="store_true", help="skip the Notion push even if configured")
    r.add_argument("--exclude-seen", action="store_true",
                   help="skip jobs already surfaced in earlier runs (cross-run de-dup)")
    r.set_defaults(func=_cmd_run)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
