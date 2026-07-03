import json
import tempfile
import unittest
from pathlib import Path

from jobscreener.config import get_settings
from jobscreener.pipeline import run_screening
from jobscreener.report import build_html

_CV = "Skills: Python, SQL, credit risk, IFRS 9, WoE scorecard, logistic regression, VaR."

_JOBS = [
    {"title": "Credit Risk Analyst", "company": "Mox Bank", "location": "Hong Kong",
     "posted_days_ago": 2, "description": "PD scorecard WoE logistic regression IFRS 9 python sql"},
    {"title": "Senior Risk Manager", "company": "Citi", "location": "Hong Kong",
     "posted_days_ago": 2, "description": "10+ years, lead the team, senior"},
    {"title": "Warehouse Associate", "company": "LogiCo", "location": "Hong Kong",
     "posted_days_ago": 1, "description": "packing and shipping in the warehouse"},
    {"title": "Old Credit Role", "company": "Old Bank", "location": "Hong Kong",
     "posted_days_ago": 99, "description": "credit risk python sql"},
]


class PipelineTests(unittest.TestCase):
    def _settings(self, tmp: Path):
        (tmp / "cv.md").write_text(_CV, encoding="utf-8")
        (tmp / "jobs.json").write_text(json.dumps(_JOBS), encoding="utf-8")
        s = get_settings()
        s.cv_path = tmp / "cv.md"
        s.jobs_path = tmp / "jobs.json"
        s.use_llm = False
        return s

    def test_run_screening_filters_and_ranks(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._settings(Path(d))
            result = run_screening(s)
            # Only the Credit Risk Analyst should survive the hard filters.
            self.assertEqual(len(result.top), 1)
            self.assertEqual(result.top[0].job.company, "Mox Bank")
            self.assertEqual(result.meta["n_fetched"], 4)
            self.assertEqual(result.meta["dropped"]["stale"], 1)
            # "Senior Risk Manager, 10+ years" is knocked out by the experience gate.
            self.assertEqual(result.meta["dropped"]["over_experienced"], 1)
            self.assertFalse(result.meta["llm_used"])

    def test_exclude_seen_catches_repost_with_new_id(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            s = self._settings(tmp)
            s.output_dir = tmp                      # isolate seen_jobs.json
            # First run surfaces the Credit Risk Analyst and records it as seen.
            r1 = run_screening(s, exclude_seen=True)
            self.assertEqual(len(r1.top), 1)
            # Re-post the SAME role under a new URL -> a new board id.
            reposted = list(_JOBS)
            reposted[0] = {**_JOBS[0], "url": "https://example.com/brand-new-id"}
            (tmp / "jobs.json").write_text(json.dumps(reposted), encoding="utf-8")
            r2 = run_screening(s, exclude_seen=True)
            # Recognised as already-seen via company+title, despite the new id.
            self.assertEqual(len(r2.top), 0)
            self.assertGreaterEqual(r2.meta["n_seen_skipped"], 1)

    def test_result_exposes_fetched_raws(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._settings(Path(d))
            result = run_screening(s)
            self.assertEqual(len(result.raws), 4)   # all fetched postings, verbatim

    def test_report_html_renders(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._settings(Path(d))
            result = run_screening(s)
            html = build_html(result.top, result.meta)
            self.assertIn("Your Daily Job Matches", html)
            self.assertIn("Credit Risk Analyst", html)
            self.assertIn("charset", html)


if __name__ == "__main__":
    unittest.main()
