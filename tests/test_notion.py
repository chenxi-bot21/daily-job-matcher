import unittest

from jobscreener import notion
from jobscreener.models import JobPosting, ScoreBreakdown, ScoredJob


def _scored():
    job = JobPosting(id="1", title="Credit Risk Analyst", company="Mox Bank",
                     location="Hong Kong", description="", url="https://x/1", source="linkedin/apify")
    return ScoredJob(job=job, score=82.7, breakdown=ScoreBreakdown(),
                     matched_skills=["python", "credit risk"])


# A representative Notion database schema (name -> type).
_SCHEMA = {
    "Name": "title", "Company": "rich_text", "Location": "rich_text",
    "Score": "number", "Status": "select", "Skills": "rich_text",
    "URL": "url", "Date": "date", "Source": "select",
}


class BuildPropertiesTests(unittest.TestCase):
    def setUp(self):
        self.props = notion.build_properties(_scored(), {"source": "linkedin/apify"}, _SCHEMA)

    def test_title_and_core_fields(self):
        self.assertEqual(self.props["Name"]["title"][0]["text"]["content"], "Credit Risk Analyst")
        self.assertEqual(self.props["Company"]["rich_text"][0]["text"]["content"], "Mox Bank")
        self.assertEqual(self.props["Score"]["number"], 82.7)
        self.assertEqual(self.props["Status"]["select"]["name"], "To Apply")
        self.assertEqual(self.props["URL"]["url"], "https://x/1")

    def test_only_existing_columns_are_written(self):
        # A schema missing most columns should still work (fill what exists).
        minimal = {"Name": "title", "Score": "number"}
        props = notion.build_properties(_scored(), {}, minimal)
        self.assertEqual(set(props), {"Name", "Score"})

    def test_value_for_type_number_handles_bad_value(self):
        self.assertIsNone(notion._value_for_type("number", "abc")["number"])

    def test_multi_select_splits_csv(self):
        out = notion._value_for_type("multi_select", "python, sql, r")
        self.assertEqual([o["name"] for o in out["multi_select"]], ["python", "sql", "r"])


if __name__ == "__main__":
    unittest.main()
