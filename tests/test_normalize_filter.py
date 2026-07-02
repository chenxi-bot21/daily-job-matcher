import unittest

from jobscreener.config import get_settings
from jobscreener.dedup import deduplicate
from jobscreener import filters
from jobscreener.filters import apply_filters
from jobscreener.models import JobPosting
from jobscreener.normalize import infer_seniority, normalize


class NormalizeTests(unittest.TestCase):
    def test_strips_html_and_builds_id(self):
        job = normalize({"title": "Risk <b>Analyst</b>", "company": "Bank",
                         "description": "<p>Python  SQL</p>", "url": "u1"})
        self.assertEqual(job.title, "Risk Analyst")
        self.assertEqual(job.description, "Python SQL")
        self.assertTrue(job.id)

    def test_infer_seniority(self):
        self.assertEqual(infer_seniority("Senior Analyst", ""), "senior")
        self.assertEqual(infer_seniority("Summer Intern", ""), "internship")
        self.assertEqual(infer_seniority("Graduate Analyst", ""), "entry")
        self.assertEqual(infer_seniority("Analyst", "3 years"), "entry")


class DedupTests(unittest.TestCase):
    def _job(self, company, title, url, days):
        return JobPosting(id=url, title=title, company=company, location="HK",
                          description="", url=url, posted_days_ago=days)

    def test_same_company_similar_title_merges_keeping_fresh(self):
        jobs = [self._job("Mox Bank", "Credit Risk Analyst", "a", 5),
                self._job("Mox Bank", "Credit Risk Analyst", "b", 2)]
        out = deduplicate(jobs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].posted_days_ago, 2)  # kept the fresher

    def test_different_companies_not_merged(self):
        jobs = [self._job("Mox Bank", "Credit Risk Analyst", "a", 2),
                self._job("Old Bank", "Credit Risk Analyst", "b", 5)]
        self.assertEqual(len(deduplicate(jobs)), 2)


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.s = get_settings()

    def _job(self, **kw):
        base = dict(id="x", title="Analyst", company="C", location="Hong Kong",
                    description="python credit risk", url="u", posted_days_ago=1,
                    seniority="entry")
        base.update(kw)
        return JobPosting(**base)

    def test_drops_stale_senior_offdomain_and_location(self):
        jobs = [
            self._job(id="ok"),
            self._job(id="stale", posted_days_ago=99),
            self._job(id="senior", seniority="senior", title="Senior Analyst"),
            self._job(id="offdomain", description="cooking recipes", title="Chef"),
            self._job(id="badloc", location="Mars"),
        ]
        kept, dropped = apply_filters(jobs, self.s)
        kept_ids = {j.id for j in kept}
        self.assertIn("ok", kept_ids)
        self.assertEqual(dropped["stale"], 1)
        self.assertEqual(dropped["seniority"], 1)
        self.assertEqual(dropped["location"], 1)


class KnockoutTests(unittest.TestCase):
    def setUp(self):
        self.s = get_settings()

    def _job(self, desc, title="Analyst"):
        return JobPosting(id="x", title=title, company="C", location="Singapore",
                          description=desc, seniority="entry")

    def test_min_years_ignores_company_age(self):
        self.assertIsNone(filters.min_years_required("For over 180 years we have served clients."))
        self.assertEqual(filters.min_years_required("Minimum 2-5 years experience"), 2)
        self.assertEqual(filters.min_years_required("5+ years of experience required"), 5)
        self.assertEqual(filters.min_years_required("At least 3 years"), 3)

    def test_experience_knockout(self):
        self.assertFalse(filters.passes_experience(self._job("Minimum 10 years of experience"), self.s))
        # "Minimum 3 years" means at least 3 -> a new grad (~1 yr) is knocked out.
        self.assertFalse(filters.passes_experience(self._job("Minimum 3 years of experience"), self.s))
        self.assertFalse(filters.passes_experience(self._job("3+ years of experience"), self.s))
        self.assertTrue(filters.passes_experience(self._job("1-2 years of experience"), self.s))
        self.assertTrue(filters.passes_experience(self._job("No experience required"), self.s))

    def test_eligibility_knockout(self):
        self.assertFalse(filters.passes_eligibility(self._job("Only Singaporeans need apply."), self.s))
        self.assertFalse(filters.passes_eligibility(self._job("We do not sponsor work visas."), self.s))
        self.assertTrue(filters.passes_eligibility(self._job("Based in Singapore, hybrid."), self.s))

    def test_degree_knockout(self):
        self.assertFalse(filters.passes_degree(self._job("Postdoctoral Fellow position."), self.s))
        self.assertFalse(filters.passes_degree(self._job("A PhD is required for this role."), self.s))
        self.assertTrue(filters.passes_degree(self._job("PhD or equivalent; MSc welcome."), self.s))
        self.assertTrue(filters.passes_degree(self._job("Bachelor's or Master's degree."), self.s))


if __name__ == "__main__":
    unittest.main()
