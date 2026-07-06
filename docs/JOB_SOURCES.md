# Job Sources for Singapore & Hong Kong — research & deployment notes

*Question: beyond LinkedIn (which we pull via the paid Apify actor), what other
sources can feed the screener for SG/HK — ideally **without a paid API** — and
how do we actually deploy them? Researched & tested 2026-07-03.*

## TL;DR — recommended free stack

| Source | SG | HK | Cost | Deploy effort | Verdict |
|---|:--:|:--:|---|---|---|
| **MyCareersFuture** (gov API) | ✅ | — | Free, official | **None** — runs on our Python 3.14 | **Add first.** Best free SG source. |
| **Indeed** via JobSpy | ✅ | ✅ | Free | uv-managed Python 3.12 sidecar | **Add.** Only good free HK source. |
| LinkedIn via **Apify** | ✅ | ✅ | ~$0.3/run | already deployed | Keep — best LinkedIn coverage. |
| Google Jobs via JobSpy | ~ | ~ | Free | (same sidecar) | Optional; query-format finicky, 0 rows in tests. |
| Glassdoor / ZipRecruiter | ✗ | ✗ | — | — | Skip — Glassdoor 403s; ZipRecruiter is US/CA only. |
| JobsDB / JobStreet (SEEK) | ✅ | ✅ | — | hard | Skip for now — no public API, scraping-hostile. |
| eFinancialCareers | ✅ | ✅ | — | hard | Skip — no API; good for manual browsing only. |

Net: **MyCareersFuture (SG) + Indeed-via-JobSpy (SG & HK) + Apify LinkedIn** covers
the ground for free-plus-cheap, and the pipeline's dedup merges the overlap.

## 1. MyCareersFuture — the free SG win (no deploy, no scraping)

Workforce Singapore's government portal exposes a **public JSON search API** — no
key, no ToS grey-area, clean structured data. Verified working:

```
POST https://api.mycareersfuture.gov.sg/v2/search?limit=20&page=0
Content-Type: application/json
{"search": "credit risk analyst", "sessionId": "..."}
```
Returned 26 on-target roles (Bank of China, AIA, Randstad, PERSOL…) with title,
company, salary, and a job URL. **Pure stdlib HTTP — it runs on our existing
Python 3.14**, so it drops straight in as a new `JobSource` (`MyCareersFutureSource`
in `sources.py`) with no environment work. SG-only (HK has no equivalent gov portal).

## 2. Indeed via JobSpy — the free SG+HK workhorse (needs a 3.12 sidecar)

[JobSpy](https://github.com/speedyapply/JobSpy) (`python-jobspy`) scrapes Indeed,
LinkedIn, Glassdoor, Google, ZipRecruiter, Bayt, Naukri, BDJobs with no API key.
For **SG/HK the only reliably-useful board is Indeed** — its scraper uses Indeed's
**GraphQL API** (60+ countries, minimal rate-limiting). Verified working:
`indeed-SG → 10 rows/2.0s`, `indeed-HK → 10 rows/1.7s`, all on-target credit/risk roles.

### The version bind (why "JobSpy doesn't work on 3.14" — and the fix)
- Our 3.14 env has an **old** `python-jobspy 1.1.13` (numpy `>=1.26`, works on 3.14)
  — but it's too old: **Indeed 403s**, and Google/Glassdoor aren't supported.
- The **latest** `python-jobspy` (1.1.82) has the working Indeed GraphQL scraper —
  but it **pins `numpy==1.26.3`**, which has **no Python 3.14 wheel**. So you cannot
  `pip install` the good JobSpy into our 3.14 interpreter. This is the real blocker
  (not JobSpy-on-3.14 in general; the older-numpy pin specifically).
- ⚠️ **Do not `pip install -U python-jobspy` in the 3.14 env** — it would try to pull
  numpy 1.26.3 and break. Keep JobSpy out of the main env; run it in a sidecar.

### Deployment — uv-managed Python 3.12 sidecar (chosen; no admin, no Docker)
The machine has no Docker and only Python 3.14, so we isolate a 3.12 just for JobSpy.
`uv` (a single user-local binary; install with `pip install uv`) provisions 3.12 and
runs JobSpy in an ephemeral env — **verified end-to-end**:

```bash
# one line: uv downloads Python 3.12 + latest JobSpy and runs the fetch script
uv run --python 3.12 --with python-jobspy scripts/fetch_indeed.py \
    --location "Singapore" --country Singapore --out output/indeed_sg.csv
```
The sidecar writes a **CSV**; the screener (on 3.14) ingests it with the existing
`JobSpyCsvSource`:
```bash
python -m jobscreener run --source sample --jobs output/indeed_sg.csv
```
(`--source sample --jobs *.csv` routes to `JobSpyCsvSource`; the `map_jobspy_row`
mapper already normalises JobSpy's columns.) No token ever touches the tool.

**Alternatives considered:** Docker `python:3.12-slim` (heavier, Docker not installed);
GitHub Actions cron (datacenter IPs get blocked by LinkedIn/Indeed, and Notion writes
need an interactive session) — both rejected in favour of the local uv sidecar.

## 3. What was ruled out & why
- **Glassdoor** — 403 on both old and new JobSpy for SG.
- **ZipRecruiter** — US/Canada only.
- **Google Jobs** — supported by new JobSpy but returns 0 without exact query
  phrasing ("… jobs in Singapore since yesterday"); revisit as a bonus, not a pillar.
- **JobsDB / JobStreet** (SEEK-owned, dominant in HK) & **eFinancialCareers** — no
  public API; scraping is ToS-restricted and brittle. Best used by the human for
  manual browsing, or via Apify actors (paid) if ever needed.

## Status — both implemented & verified 2026-07-03
1. ✅ **`MyCareersFutureSource`** added (`--source mcf`, runs on 3.14). Live: 20 fetched
   → descriptions pulled → real credit-analyst roles surfaced.
2. ✅ **`scripts/fetch_indeed.py`** (uv sidecar) added + documented in the RUNBOOK. Live:
   Indeed SG 25 rows → CSV → ingested via `--source sample --jobs`. HK works the same way.
3. Apify LinkedIn kept as-is; `deduplicate()` merges cross-source repeats.

⚠️ **Windows uv gotcha:** `uv run --python 3.12` can fail with *"Missing expected target
directory … minor version link"* — uv needs Developer Mode to create the symlink. Work
around it by pointing `--python` at the interpreter path directly (see RUNBOOK / the
script docstring). The 3.12 itself installs fine; only the convenience symlink fails.

## Sources
- [JobSpy (GitHub)](https://github.com/speedyapply/JobSpy) · [python-jobspy (PyPI)](https://pypi.org/project/python-jobspy/)
- MyCareersFuture API: `https://api.mycareersfuture.gov.sg/v2/search`
- [uv](https://docs.astral.sh/uv/) — the sidecar Python/env manager.
