"""Free Indeed (SG + HK) fetcher — the JobSpy sidecar, multi-term in one run.

The latest ``python-jobspy`` (working Indeed GraphQL scraper) pins an old numpy
with no Python 3.14 wheel, so it can't live in the screener's 3.14 env. Run it in
an isolated Python 3.12 via ``uv`` (a single user-local binary):

    uv run --python 3.12 --with python-jobspy --with pandas scripts/fetch_indeed.py

That fetches the last 24h across several finance terms for both Singapore and
Hong Kong into one de-duplicated CSV (default: output/indeed_24h.csv). Then
ingest it with the screener (on 3.14) — no token, no paid API:

    python -m jobscreener run --source sample --jobs output/indeed_24h.csv --exclude-seen

(Windows: if `--python 3.12` fails with "Missing expected target directory …
minor version link", uv couldn't create the symlink without Developer Mode —
point --python at the interpreter directly, e.g.
``--python "%APPDATA%\\uv\\python\\cpython-3.12.13-windows-x86_64-none\\python.exe"``.)

Standalone (stdlib + jobspy + pandas only); does NOT import ``jobscreener``
because it runs in a different interpreter.
"""
from __future__ import annotations

import argparse
import inspect
import sys

# Default finance terms matched to the candidate's targets (credit/risk/data).
DEFAULT_TERMS = ["credit risk analyst", "risk analyst", "credit analyst",
                 "data analyst", "quantitative analyst", "graduate analyst"]
# "Location:country_indeed" pairs.
DEFAULT_LOCATIONS = ["Singapore:Singapore", "Hong Kong:Hong Kong"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Fetch Indeed SG+HK (last 24h) via JobSpy → one CSV.")
    p.add_argument("--terms", default=",".join(DEFAULT_TERMS),
                   help="comma-separated search terms")
    p.add_argument("--locations", default=",".join(DEFAULT_LOCATIONS),
                   help="comma-separated 'Location:country_indeed' pairs")
    p.add_argument("--results", type=int, default=25, help="results wanted per (term, location)")
    p.add_argument("--hours-old", type=int, default=24, help="max age in hours (24 = last day)")
    p.add_argument("--out", default="output/indeed_24h.csv", help="output CSV path")
    args = p.parse_args(argv)

    try:
        import pandas as pd
        from jobspy import scrape_jobs
    except ImportError:
        print("ERROR: run me via uv, e.g.\n"
              "  uv run --python 3.12 --with python-jobspy --with pandas scripts/fetch_indeed.py",
              file=sys.stderr)
        return 2

    supported = set(inspect.signature(scrape_jobs).parameters)   # signature drifts by version
    terms = [t.strip() for t in args.terms.split(",") if t.strip()]
    locations = [pair.split(":", 1) for pair in args.locations.split(",") if pair.strip()]

    frames = []
    for loc, country in locations:
        loc, country = loc.strip(), country.strip()
        for term in terms:
            kwargs = {"site_name": ["indeed"], "search_term": term, "location": loc,
                      "results_wanted": args.results, "country_indeed": country}
            if "hours_old" in supported:
                kwargs["hours_old"] = args.hours_old
            try:
                df = scrape_jobs(**kwargs)
                n = 0 if df is None else len(df)
                print(f"  {country:10} | {term:22} -> {n}")
                if n:
                    frames.append(df)
            except Exception as e:                                # keep going on a bad query
                print(f"  {country:10} | {term:22} -> ERR {type(e).__name__}: {str(e)[:60]}")

    if not frames:
        print("no rows")
        return 0
    allrows = pd.concat(frames, ignore_index=True)
    before = len(allrows)
    allrows = allrows.drop_duplicates(subset=["job_url"]).drop_duplicates(subset=["title", "company"])
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    allrows.to_csv(args.out, index=False, encoding="utf-8")
    print(f"\nIndeed: {before} rows -> {len(allrows)} unique -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
