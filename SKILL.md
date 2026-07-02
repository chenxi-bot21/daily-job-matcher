---
name: daily-job-matcher
description: >-
  Daily AI job-matching pipeline. Scrapes LinkedIn job postings (via an Apify
  actor), screens them against the user's résumé/CV with a hard ATS-style
  "knockout gate" (work authorization / visa, minimum years of experience,
  required degree) plus a transparent weighted fit score, curates the best
  matches, and writes them to a single Notion tracker — and can read Gmail to
  keep each application's status (Applied / Rejected / Interview / Offer) up to
  date. Use this skill whenever the user wants to find, screen, rank, or filter
  job postings against their résumé, build a daily "job digest", run or automate
  a job search, decide which roles are worth applying to, track job applications,
  or update their application tracker from email — even if they don't say the
  word "skill" or name the tool. Especially relevant for new-grad / early-career
  searches where experience and visa requirements matter.
---

# Daily Job Matcher

An end-to-end job-search assistant: **scrape → knockout-gate → score → curate →
Notion**, plus **email → status updates**. The mechanical steps run as a tested
Python package (`jobscreener`); the judgement steps (reading full job
descriptions, curating true fit, writing to Notion) are done by you with the
Notion/Gmail MCP connectors.

## When to use
Trigger for: "find me jobs that fit my resume", "screen these LinkedIn roles",
"today's job matches", "which of these should I apply to", "update my
application tracker from my email", "did I get any rejections", "build a daily
job digest". Prefer this over ad-hoc searching whenever a résumé + real postings
are involved.

## One-time setup
1. **Install**: `pip install -r requirements.txt` (add `python-jobspy` only if
   using the free JobSpy source; on Python 3.14 use `pip install --only-binary=:all:`).
2. **Secrets** in `.env` (copy `.env.example`; git-ignored — never commit or paste):
   `APIFY_TOKEN` (required for the LinkedIn source), optional `ANTHROPIC_API_KEY`
   (LLM re-scoring), `NOTION_TOKEN` for the unattended path.
3. **Résumé**: put the user's CV at `data/cv.md` (copy `data/cv.example.md`). This
   is the matching source of truth — level, skills, target roles, and hard
   constraints (visa, years, degree).
4. **Search config**: `apify_input.json` (copy `apify_input.example.json`) — the
   Apify actor input: `keyword[]`, `locations[]`, `publishedAt` (`r86400` = 24h),
   `maxItems`. Set `JOBSCREENER_APIFY_ACTOR` / `JOBSCREENER_APIFY_TASK` in `.env`.
5. **Candidate constraints**: tune `CandidateProfile` in `src/jobscreener/config.py`
   (`years_experience`, `max_years_experience`, `needs_visa_sponsorship`,
   `highest_degree`, `target_roles`, `exclude_title_keywords`, …).
6. **Notion**: connect the Notion MCP and note the target database's
   `data_source_id`. Use one master table (see step 4 of the daily cycle).

## Daily cycle
Run from the project directory. (If `python` is a broken Windows Store stub, use
`py` or the full interpreter path.)

1. **Scrape** the recent window (Apify actor; ~$0.1/run):
   `python -m jobscreener run --source apify --apify-input apify_input.json`
   → writes `output/apify_raw.json`.
2. **Screen + dump full JDs.** Apply the pipeline (knockout gate + score) to the
   raw file and export the passing candidates **with full descriptions** so you
   can read them. The heuristic *rank* is a first pass, not the final word.
3. **Read the full JDs and curate by true fit.** The knockout gate already drops
   ineligible / over-experienced / wrong-degree roles; your job is judgement:
   down-rank roles that only keyword-match (e.g. trading/HFT, AI-research
   engineering, pure SWE) but don't fit the candidate, and flag caveats the gate
   can't see. **Quality over quantity** — a short honest list beats a padded one.
4. **Append to the ONE master Notion table** (via the Notion MCP). Do **not**
   create a new table each day. Columns: Name, Company, Location, Fit
   (Strong/Good/Moderate), Notes (why / caveats), Seniority, Status (new matches
   = `To Apply`), URL, Date, Source (`LinkedIn`). Prefix Name with a priority number.
5. **Report** the ranked shortlist and which to apply to first.

Use `--exclude-seen` so the same job isn't surfaced on consecutive days.

## Knockout gate (the core idea)
Standard job-matching separates **hard non-negotiables** (disqualify instantly)
from **soft weighted signals** (rank). Implemented in `filters.py`:
- **Eligibility** — citizenship-only / no-sponsorship / clearance phrases → out.
- **Experience** — the JD's *minimum* required years > `max_years_experience` → out.
  ("Minimum 3 years" means ≥3; a new grad doesn't meet it.)
- **Degree** — PhD / postdoc required and the candidate is below → out.

Soft score (0–100) blends skill match (TF-IDF + skill overlap), title relevance,
domain fit, seniority alignment, and location. Full rationale: `METHODOLOGY.md`.

## Application tracking from email
When asked to "read email / update statuses": search Gmail (Gmail MCP) for
job-application confirmations, rejections, and interview invites, then update the
matching rows' **Status** in the same master table (`Applied` / `Rejected` /
`Interview` / `Offer` / `Started`), or add rows for applications not yet tracked
(Source = `Email`). One table for both matching and tracking.

## References (read as needed)
- `RUNBOOK.md` — full operating manual, gotchas, module map, how to extend.
- `METHODOLOGY.md` — how the funnel and scoring decide (the research).
- `README.md` — install, sources (Apify / JobSpy / sample), CLI flags.
- `src/jobscreener/` — the package; tests: `python -m unittest discover -s tests -t .`.

## Notes
- No in-house LinkedIn scraper (ToS). Sources are pluggable behind `JobSource`
  in `sources.py`: Apify (managed, recommended), JobSpy (free), sample/CSV/JSON.
- The Notion/Gmail MCP connectors only work inside an interactive session, so
  the cycle is on-command, not a background cron.
