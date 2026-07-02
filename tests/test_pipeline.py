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
