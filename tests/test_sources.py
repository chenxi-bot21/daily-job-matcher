import datetime
import json
import tempfile
import unittest
from pathlib import Path

from jobscreener.sources import (ApifyFileSource, ApifySource, _coerce_str, _days_since,
                                 map_apify_item, map_jobspy_row)


class ApifyMappingTests(unittest.TestCase):
    def test_maps_common_actor_fields(self):
        item = {"title": "Credit Risk Analyst", "companyName": "Mox Bank",
                "location": "Hong Kong", "descriptionText": "PD scorecard, Python",
                "jobUrl": "https://linkedin.com/jobs/1", "contractType": "Full-time"}
        out = map_apify_item(item)
        self.assertEqual(out["title"], "Credit Risk Analyst")
        self.assertEqual(out["company"], "Mox Bank")
        self.assertEqual(out["url"], "https://linkedin.com/jobs/1")
        self.assertEqual(out["source"], "linkedin/apify")

    def test_tolerates_alternate_field_names(self):
        item = {"jobTitle": "Analyst", "company": "C", "description": "text",
                "link": "u", "jobType": "Contract"}
        out = map_apify_item(item)
        self.assertEqual(out["title"], "Analyst")
        self.assertEqual(out["company"], "C")
        self.assertEqual(out["url"], "u")

    def test_missing_fields_default_to_empty(self):
        out = map_apify_item({})
        self.assertEqual(out["title"], "")
        self.assertEqual(out["posted_days_ago"], 0)


class ApifyFileSourceTests(unittest.TestCase):
    def test_reads_and_maps_dataset_json(self):
        items = [{"title": "Credit Risk Analyst", "companyName": "Mox Bank",
                  "location": "Hong Kong", "descriptionText": "python", "jobUrl": "u"}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "apify.json"
            p.write_text(json.dumps(items), encoding="utf-8")
            raws = ApifyFileSource(p).fetch()
        self.assertEqual(len(raws), 1)
        self.assertEqual(raws[0]["company"], "Mox Bank")
        self.assertEqual(raws[0]["source"], "linkedin/apify")

    def test_unwraps_items_key(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "apify.json"
            p.write_text(json.dumps({"items": [{"title": "Analyst"}]}), encoding="utf-8")
            self.assertEqual(len(ApifyFileSource(p).fetch()), 1)


class ApifyInputTests(unittest.TestCase):
    def test_verbatim_input_json_is_used(self):
        custom = {"keywords": ["credit risk"], "location": "Hong Kong", "maxItems": 50}
        src = ApifySource(token="x", input_json=custom)
        self.assertEqual(src._build_input(), custom)

    def test_default_actor_is_cheap_scraper(self):
        self.assertEqual(ApifySource(token="x", actor="cheap_scraper~linkedin-job-scraper").actor,
                         "cheap_scraper~linkedin-job-scraper")

    def test_task_uses_task_endpoint(self):
        src = ApifySource(token="x", task="zog2TlZlx6ZCpnGR2")
        self.assertIn("actor-tasks/zog2TlZlx6ZCpnGR2", src._endpoint())

    def test_actor_uses_actor_endpoint(self):
        import os
        old = os.environ.pop("JOBSCREENER_APIFY_TASK", None)  # ignore any ambient .env
        try:
            src = ApifySource(token="x", actor="cheap_scraper~linkedin-job-scraper")
            self.assertIn("acts/cheap_scraper~linkedin-job-scraper", src._endpoint())
        finally:
            if old is not None:
                os.environ["JOBSCREENER_APIFY_TASK"] = old

    def test_task_without_override_sends_saved_input(self):
        # No input_json + a task -> None body -> the task's saved input is used.
        self.assertIsNone(ApifySource(token="x", task="t")._build_input())


class JobSpyMappingTests(unittest.TestCase):
    def test_maps_row_and_computes_days(self):
        five_days_ago = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
        row = {"title": "Risk Analyst", "company": "Bank", "location": "Hong Kong",
               "description": "python credit risk", "job_url": "https://x/1",
               "date_posted": five_days_ago, "job_type": "fulltime", "site": "linkedin"}
        out = map_jobspy_row(row)
        self.assertEqual(out["title"], "Risk Analyst")
        self.assertEqual(out["url"], "https://x/1")
        self.assertEqual(out["posted_days_ago"], 5)
        self.assertEqual(out["source"], "jobspy/linkedin")

    def test_coerce_str_handles_nan(self):
        self.assertEqual(_coerce_str(float("nan")), "")
        self.assertEqual(_coerce_str(None), "")
        self.assertEqual(_coerce_str("hi"), "hi")

    def test_days_since_unknown_is_zero(self):
        self.assertEqual(_days_since(None), 0)
        self.assertEqual(_days_since(float("nan")), 0)
        self.assertEqual(_days_since(datetime.date.today()), 0)


if __name__ == "__main__":
    unittest.main()
