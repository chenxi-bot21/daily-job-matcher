# Daily Job-Digest Playbook (repeatable)

The exact, repeatable steps to produce **one curated daily shortlist of truly-fit
roles across LinkedIn + Indeed + MyCareersFuture**, with apply links, in the
Notion "Job Search Tracker". Trigger: user says *"跑今天/昨天的岗位"*. On-command
(the Notion/Gmail MCPs need an interactive session — no cron).

Run everything from `D:\download\RESUME\job_screener\`. `python` on PATH is a
broken stub — use the full interpreter:
`C:\Users\15910\AppData\Local\Python\bin\python.exe` (written `PY` below).
Sources + rationale: [`JOB_SOURCES.md`](JOB_SOURCES.md).

---

## The 6 steps

### 1. LinkedIn — Apify scrape, last 24h  (~$0.3)
```
PY -m jobscreener run --source apify --apify-input apify_input.json --exclude-seen
```
Writes `output/apify_raw.json` (raw), `candidates_full.json`, `top_jobs.json`, HTML.

### 2. Indeed — free, SG+HK, last 24h  (uv 3.12 sidecar, no cost)
```
PY -m uv run --python 3.12 --with python-jobspy --with pandas scripts/fetch_indeed.py
```
Writes `output/indeed_24h.csv` (multi-term × SG/HK, de-duped).
⚠️ Windows: if `--python 3.12` errors with *"…minor version link"*, pass the path
instead: `--python "%APPDATA%\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"`.
⚠️ Never `pip install -U python-jobspy` into the 3.14 env (breaks numpy).

### 3. Combine + screen all three → one ranked file  (on 3.14)
```
PY scripts/combine_sources.py
```
Screens LinkedIn(apify_raw) + Indeed(csv) + MyCareersFuture(live, ≤24h) through the
same knock-out gate + score, merges, de-dups by company+title, and writes
**`output/combined_full.json`** — every passer with full JD, source, apply URL, score.
(MyCareersFuture = free official SG API, fetched live here; no separate step.)

### 4. Hand-curate by TRUE fit  (the judgement step — see the bar below)
Read `output/combined_full.json`. The heuristic score is a first pass only. Apply
the **curation bar** below. **Quality over quantity — a short honest list beats a
padded one.** (If asked for a fixed count and true fits fall short, say so rather
than padding with tangential roles.)

### 5. De-dup against Notion, then append  (Notion MCP)
Before adding, query the tracker so you don't re-add reposts or already-applied roles:
```sql
SELECT "Name","Company","Status" FROM "collection://a9a4d24b-164d-4744-857a-7ebf3c787640"
WHERE "Company" LIKE '%<company>%' OR "Name" LIKE '%<title-fragment>%'
```
LinkedIn re-posts a role under a **new id**, so a role can resurface after it was
already Applied — the id-based `--exclude-seen` misses that; the Notion check catches it.
Append survivors to the ONE master table (data_source_id
`a9a4d24b-164d-4744-857a-7ebf3c787640`) as new rows:
- **Name** = "N. <title>" (priority number), **Company**, **Location**,
  **Fit** (Strong/Good/Moderate), **Notes** (why + caveats), **Seniority**
  (entry/internship/mid), **Status** = `To Apply`, **URL** = the apply link,
  **Source** (`LinkedIn` / `Indeed` / `MyCareersFuture`), **Date** = the run date.

### 6. Report + trace
Give the user the ranked shortlist **with apply URLs**. Append one entry to
`../WORKLOG.md` (Did / Why / Result / Next).

---

## The curation bar — what is "truly fit"
Candidate = new-grad, **needs visa sponsorship**, SG-based (open to HK/China).
Targets: credit-risk / risk / model-validation / credit analyst, entry
quant-research, finance & data analyst/scientist, biostatistician, graduate
programmes. Hard-out (the gate handles most): >2 yrs min experience, PhD-only,
citizens-only / no-sponsorship, trading/HFT/market-making, senior/VP, pure SWE.

**KEEP (truly fit):**
- Credit risk / risk / market risk / model validation / model risk analyst.
- AML / KYC / CDD / financial-crime analyst (an explicit target block).
- Actuarial / quant-risk (valuation, Solvency/IFRS) at insurers/reinsurers.
- Genuine **entry finance analyst** (financial modelling, valuation, risk eval).
- Genuine **data / research analyst** matching her Python/R/SQL/stats profile.
- Graduate-programme / new-grad analyst roles in the above.

**CUT (looks close, isn't):**
- Trading / HFT / options MM / stat-arb / **structured-derivatives** desks (markets).
- Pure SWE / data engineer / DevOps / SRE / QA / IT "system analyst".
- AI/ML **research or engineering** (LLM/CV/robotics), PhD-heavy research.
- Ops / middle-office / settlement / static-data roles dressed as "analyst".
- IT **business analyst** / consulting (requirements & process mapping).
- Ad-tech / programmatic-audience "data advisory"; marketing/comms analyst.
- Defence labs (e.g. DSO) and government ministries — usually citizens/PR only.
- **Wrong location** (e.g. a China-only posting), or **very short contracts** and
  **far-future internships** (Dec/Fall next year) — include only if genuinely on-core.

When in doubt, **cut** and note it. Mark honest Fit: Strong (bullseye) / Good
(on-target, minor gap) / Moderate (adjacent or has a caveat — state it in Notes).

---

## Known gotchas (so tomorrow doesn't re-hit them)
- **Reposts already-applied** — the strongest roles often reappear because LinkedIn
  reposts them; always do the step-5 Notion check. (`--exclude-seen` now also keys on
  company+title, which catches most, but the Notion check is the backstop.)
- **Indeed 24h can be thin** after the gate (non-SG/HK locations, experience). Normal.
- **MCF fresh-24h is small on quiet days** — it's a supplement, not a pillar.
- **Apify `maxItems` is a global cap** (currently 400) — keep it high or one broad
  keyword starves the rest. Tune keywords in `apify_input.json`.
- Verify a top pick's **min-years / visa** in its JD before telling the user to apply.
