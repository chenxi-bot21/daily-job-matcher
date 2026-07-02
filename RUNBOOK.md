# jobscreener — Runbook & Handoff Guide

Operational manual for running the **daily job-matching cycle** and for anyone
(or any new AI session) taking over. For *what it is* see [README.md](README.md);
for *how it decides* see [METHODOLOGY.md](METHODOLOGY.md). Instance-specific
secrets and IDs live in `.env` (git-ignored) and in the session memory, **not**
here.

## The candidate (matching context)
The candidate profile lives in `data/cv.md` — **read it first.** It states the
candidate's level (new-grad vs experienced), work-authorization / visa status,
skills, the role types they want, and role types to down-rank. Everything
downstream — the knockout thresholds in `config.py` and your curation judgement —
should follow that file, not assumptions. Keep the hard constraints in
`CandidateProfile` (`years_experience`, `max_years_experience`,
`needs_visa_sponsorship`, `highest_degree`) in sync with the CV.

## Daily cycle (when the user asks for "today's jobs")
Run everything from the `job_screener/` directory. On this machine the `python`
on PATH is a broken Store stub — use the full interpreter path (see memory) or `py`.

1. **Scrape** the last 24 h (costs ~$0.10 of Apify credit):
   `python -m jobscreener run --source apify --apify-input apify_input.json`
   — this runs the saved Apify LinkedIn task and writes `output/apify_raw.json`.
   (Search terms / locations / freshness live in `apify_input.json`.)
2. **Screen + dump full JDs.** The heuristic *rank* is noisy — do **not** trust it
   blindly. Run the screening on `apify_raw.json` and export the candidates that
   pass the knockout gate **with their full descriptions** to read.
3. **Read the full JDs and hand-curate by true fit.** The knockout gate already
   removes ineligible / over-experienced / PhD-only roles; your job is the soft
   judgement: down-rank trading / AI-engineer / robotics / pure-SWE, and flag any
   eligibility (citizens-only) or experience caveats the gate missed.
4. **Append the curated shortlist to the ONE master Notion table** ("Job Search
   Tracker", via the Notion MCP in-session). **Do not create a new table each day** —
   there is a single master table for both matches and application tracking.
   Columns: Name, Company, Location, **Fit** (Strong/Good/Moderate), **Notes**
   (caveats/why), Seniority, **Status** (new matches = `To Apply`), URL, Date,
   **Source** (`LinkedIn`). Prefix each Name with a priority number.
5. **Report** the ranked list to the user and which to apply to first.

> Use `--exclude-seen` on step 1 to skip jobs already surfaced on earlier days
> (ids logged to `output/seen_jobs.json`), so the digest never repeats.

### Application tracking (same table)
When asked to "read email / update statuses": search Gmail for job-application
confirmations, rejections, and interview invites (see the Gmail MCP), then update
the matching rows' **Status** in the master table (`Applied` / `Rejected` /
`Interview` / `Offer` / `Started`), or add rows for applications not yet in it
(Source = `Email`). Everything lives in the one "Job Search Tracker" table.

## Why this shape (important gotchas)
- **Python 3.14** blocks live JobSpy (its deps pin an old numpy with no 3.14
  wheel) and Indeed returns 403 — that's why the source is **Apify** (runs on
  Apify's servers, no local scraping).
- The **Notion MCP only works inside an interactive session**, so a cron job
  can't write to Notion. The daily cycle is therefore **on-command**, not a
  scheduled task (the earlier scheduled task was removed).
- **Secrets** (`APIFY_TOKEN`, optional `ANTHROPIC_API_KEY`, `NOTION_TOKEN`, SMTP)
  live only in `.env` (git-ignored). Never commit or paste them.

## Knockout gate (hard requirements) — `filters.py` + `CandidateProfile`
Non-negotiables that disqualify instantly, before scoring:
- **Eligibility** — citizenship-only / no-sponsorship / clearance → out.
- **Experience** — JD's *minimum* required years > `max_years_experience` (default 2) → out. A "minimum 3 years" JD means ≥3, which a new grad (~1 yr) doesn't meet.
- **Degree** — PhD / postdoc required → out (`PhD or equivalent` is respected).

Tune in `config.py`: `max_years_experience`, `needs_visa_sponsorship`,
`highest_degree`; plus `exclude_title_keywords` (trader/HFT/sales), `target_roles`,
`target_domains`, `skills`, `preferred_locations`, `ScoringWeights`, `top_n`.

## How to extend
- **New job source** → add a class in `sources.py` with `name` + `fetch() ->
  list[dict]`, and (if needed) a field mapper; wire it into `cli.py`'s `--source`.
- **Change the search** → edit `apify_input.json` (`keyword[]`, `locations[]`,
  `publishedAt` — `r86400` = 24 h, `r604800` = 7 days, `maxItems`).
- **Change matching** → `config.py` (`CandidateProfile` / `ScreeningRules` /
  `ScoringWeights`). Add a new hard filter as a `passes_*` function in `filters.py`
  and register it in `_CHECKS`.
- **Tests** → `python -m unittest discover -s tests -t .` (keep them green).

## Module map
`config` (settings) · `cv` (CV → skills) · `sources` (sample / remotive / apify /
apify-file / jobspy / jobspy-csv) · `normalize` · `dedup` · `filters` (knockout
gate) · `scoring` (5-factor soft score) · `llm` (optional Claude re-score) ·
`notion` / `email_out` (outputs) · `history` (cross-run dedup) · `report` (HTML) ·
`pipeline` (orchestration) · `cli`.
