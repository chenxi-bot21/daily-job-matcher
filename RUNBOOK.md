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
> **Full multi-source daily process (LinkedIn + Indeed + MyCareersFuture → curate
> → Notion with apply links): [`docs/DAILY_PLAYBOOK.md`](docs/DAILY_PLAYBOOK.md).**
> The steps below are the LinkedIn/Apify core; the playbook wraps all three sources
> and the "truly-fit" curation bar.

Run everything from the `job_screener/` directory. On this machine the `python`
on PATH is a broken Store stub — use the full interpreter path (see memory) or `py`.

1. **Scrape + screen** the last 24 h (costs ~$0.2–0.3 of Apify credit at
   `maxItems: 400`):
   `python -m jobscreener run --source apify --apify-input apify_input.json --exclude-seen`
   — runs the saved Apify LinkedIn task and writes, in `output/`: `top_jobs.json`
   (top-N), `candidates_full.json` (**every** knock-out-gate survivor **with its
   full JD**, score and reasons), `fetched.json` (all raw postings, re-screenable
   offline via `--source sample --jobs output/fetched.json`), and the HTML report.
   (Search terms / locations / freshness live in `apify_input.json`; `maxItems` is
   a **global** cap — keep it high or one keyword starves the rest.)
2. **Read the full JDs.** The heuristic *rank* is noisy — do **not** trust it
   blindly. Open `output/candidates_full.json` and read the descriptions; that file
   is produced automatically by step 1, so no separate export is needed.
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

### Free sources — no paid API (SG + HK)
Two free sources supplement the Apify LinkedIn pull; the pipeline's `deduplicate()`
merges any overlap. Full research + rationale: [`docs/JOB_SOURCES.md`](docs/JOB_SOURCES.md).

- **MyCareersFuture (SG, official API, zero deploy)** — runs on our Python 3.14:
  ```
  python -m jobscreener run --source mcf --search "credit risk analyst" --results 40 --exclude-seen
  ```
- **Indeed (SG + HK, via the JobSpy sidecar)** — the good JobSpy pins an old numpy
  with no 3.14 wheel, so run it in an isolated Python 3.12 via `uv`, then ingest the
  CSV on 3.14:
  ```
  uv run --python 3.12 --with python-jobspy scripts/fetch_indeed.py \
      --search "credit risk analyst" --location Singapore --country Singapore --out output/indeed_sg.csv
  python -m jobscreener run --source sample --jobs output/indeed_sg.csv --exclude-seen
  ```
  ⚠️ **Windows note:** if `--python 3.12` errors with *"Missing expected target
  directory … minor version link"* (uv can't make the symlink without Developer
  Mode), point `--python` at the interpreter directly, e.g.
  `--python "$env:APPDATA\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"`.
  Do **not** `pip install -U python-jobspy` into the 3.14 env — it breaks numpy.

### Application tracking (same table)
When asked to "read email / update statuses": search Gmail for job-application
confirmations, rejections, and interview invites (see the Gmail MCP), then update
the matching rows' **Status** in the master table (`Applied` / `Rejected` /
`Interview` / `Offer` / `Started`), or add rows for applications not yet in it
(Source = `Email`). Everything lives in the one "Job Search Tracker" table.

## Why this shape (important gotchas)
- **Apify** is the default LinkedIn source (server-side, best LinkedIn coverage).
  For free alternatives see "Free sources" above: the *latest* JobSpy pins an old
  numpy with no 3.14 wheel (so it needs the `uv` 3.12 sidecar), and its Indeed
  scraper's GraphQL path now clears the old 403 — verified for SG and HK.
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
