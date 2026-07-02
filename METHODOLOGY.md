# How the Job Screening Works — Methodology

This document explains *how the pipeline decides which jobs to surface* — the
core research behind the tool. In one line: **it is a content-based
recommendation system that ranks each posting against your CV, using a cheap
filter → transparent score → optional LLM-refinement funnel.**

## The funnel (why three stages, not one)

```
   ~100s of raw postings
        │  Stage A — HARD FILTERS (free, deterministic)   drop obvious non-fits
        ▼
   ~dozens of relevant postings
        │  Stage B — SOFT SCORE (cheap, explainable)      rank every survivor 0-100
        ▼
   ranked shortlist
        │  Stage C — LLM RE-SCORE (optional, paid)        nuance on the top ~20 only
        ▼
   Top N → report
```

The funnel exists to balance **three competing costs**:

- **Recall** (don't miss good jobs) → hard filters stay *conservative*: they only
  drop clear non-fits (wrong seniority, wrong location, off-domain, stale, dupes).
  Anything borderline is *kept and ranked*, never silently discarded.
- **Precision** (don't waste your time) → the soft score ranks so the best rise
  to the top; you read 15, not 150.
- **Money/latency** → the LLM is the only expensive step, so it runs *only on the
  shortlist* the cheap stages already promoted. Screening 200 jobs might LLM-score
  just 20.

## Stage A — Hard filters (the "knockout gate")

Standard job-matching separates **non-negotiable knock-outs** (hard requirements
that instantly disqualify — a candidate either meets them or is out) from the
*weighted* soft score. This mirrors how an ATS gates applications: eligibility
and hard requirements first, ranking second. Applied in order; the first failing
check records the drop reason (shown in the report):

| Filter | Rule | Why |
|---|---|---|
| **Eligibility** (knock-out) | drop citizenship-only / no-sponsorship / clearance JDs | a foreign national needing sponsorship can't apply |
| **Experience** (knock-out) | drop if the JD's *minimum* required years > `max_years_experience` (default 2) | a new grad (~1 yr internships) can't meet a "minimum 3 years" bar |
| **Degree** (knock-out) | drop `PhD/postdoc required` (softeners like "PhD or equivalent" respected) | MS candidate can't meet a hard PhD bar |
| **Freshness** | `posted_days_ago ≤ 21` | old postings are usually filled |
| **Location** | in preferred regions, or remote | you can only take certain locations |
| **Seniority** | drop `senior`/lead/head | early-career candidate |
| **Wrong role type** | drop `trader`/HFT/market-maker/sales by title | poor fit for this profile |
| **Excluded keywords** | drop e.g. `php`, `nurse`, `director` | obvious wrong domain/level |
| **Relevance gate** | must mention ≥1 target role/domain/skill | drop clearly unrelated roles |

The three **knock-outs** are the important part: they encode *must-haves*
(eligibility, minimum experience, required degree) that no amount of skill match
can compensate for. `min_years_required` ties a "N years" mention to an
experience context, so a company age ("for over 180 years") is ignored. All
thresholds live in `CandidateProfile` (`max_years_experience`, `highest_degree`,
`needs_visa_sponsorship`).

**De-duplication** runs before filtering: within a run, two postings merge only
if they share a URL, *or* their **company** matches closely **and** the **title**
is ≥85% similar. Across runs, `--exclude-seen` skips any job already surfaced on
a previous day (ids logged to `output/seen_jobs.json`), so a daily digest never
repeats itself.

## Stage B — Soft score (the ranking, 0–100)

Every surviving job gets a weighted blend of five interpretable dimensions.
Nothing is a black box — each recommendation shows its breakdown.

| Dimension | Weight | How it's measured |
|---|---:|---|
| **Skill match** | 40% | `0.6 × skill-overlap + 0.4 × TF-IDF cosine(CV, JD)` |
| **Title relevance** | 25% | fuzzy match of the job title to your target roles |
| **Domain fit** | 15% | how many of your target domains the JD mentions |
| **Seniority alignment** | 10% | entry/internship = high, senior = 0 |
| **Location preference** | 10% | preferred region = 100, remote = 90, else 50 |

- **Skill match** combines two views: an *explicit* overlap of a curated skill
  taxonomy (python, credit risk, IFRS 9, WoE, survival analysis, …) that appears
  in **both** CV and JD, and a *holistic* TF-IDF cosine similarity of the full
  texts (catches phrasing the taxonomy misses). This is standard content-based
  filtering: represent both sides as text vectors, measure overlap.
- **Overall** `= Σ weightᵢ · dimensionᵢ`. Weights are config (`ScoringWeights`)
  and should sum to 1.0. Tune them to lean the ranking (e.g. raise `title_relevance`
  to prioritise on-title roles, or `location_preference` if location is a hard need).

## Stage C — LLM re-scoring (optional)

When an Anthropic API key is set, Claude re-scores the shortlist. Each job → a
strict JSON verdict:

```json
{"fit_score": 0-100, "verdict": "strong|good|moderate|weak",
 "matched_strengths": [...], "gaps": [...], "one_line_reason": "..."}
```

The LLM adds judgement the heuristic can't: it reads *requirements* vs *nice-to-haves*,
notices a domain mismatch a keyword would miss, and writes the human-readable reason.
Its `fit_score` replaces the heuristic score for final ranking; if the call fails,
the heuristic score is kept (graceful degradation). Running only on the pre-ranked
shortlist keeps token cost roughly constant regardless of how many jobs were fetched.

## Design principles

1. **Rank, don't reject.** Hard filters remove only unambiguous non-fits; the score
   decides the rest. Missing a great job is worse than showing a mediocre one.
2. **Explainable by construction.** Every score is a sum of named parts, and every
   card lists matched skills and reasons — you can see *why* a job ranked where it did.
3. **Degrades gracefully.** No API key → heuristic only. No internet → bundled sample
   source. Nothing in the pipeline hard-requires a paid or online dependency.
4. **Config over code.** Target roles, skills, locations, weights, thresholds and
   `top_n` all live in `config.py` — tuning the screening never touches logic.

## Limitations & extensions

- **No feedback loop yet.** The biggest upgrade: log which surfaced jobs you actually
  applied to, and learn the weights from that (learning-to-rank) instead of hand-setting them.
- **Lexical, not semantic, skill match.** TF-IDF + keyword overlap miss synonyms
  ("PD model" vs "probability of default"). Sentence-embedding similarity would help.
- **Source coverage.** The demo uses a bundled sample; production needs a compliant
  live source (job-board/ATS APIs, not LinkedIn scraping — see `sources.py`).
- **Seniority parsing** is keyword-based; a JD saying "3–5 years" is coarser than a
  parsed range.
