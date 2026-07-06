import unittest

from jobscreener.config import get_settings
from jobscreener.cv import build_cv_profile
from jobscreener.llm import parse_llm_json
from jobscreener.models import JobPosting
from jobscreener.scoring import HeuristicScorer

_CV = ("Chenxi Zhao. Skills: Python, R, SQL, credit risk, IFRS 9, WoE scorecard, "
       "logistic regression, XGBoost, survival analysis, fixed income, VaR.")


class CVTests(unittest.TestCase):
    def test_build_profile_finds_skills(self):
        s = get_settings()
        prof = build_cv_profile(_CV, s.profile.skills)
        self.assertIn("python", prof.skills)
        self.assertIn("credit risk", prof.skills)
        self.assertIn("ifrs 9", prof.skills)


class HeuristicScorerTests(unittest.TestCase):
    def setUp(self):
        self.s = get_settings()
        self.cv = build_cv_profile(_CV, self.s.profile.skills)

    def _job(self, title, desc, loc="Hong Kong", sen="entry"):
        return JobPosting(id=title, title=title, company="C", location=loc,
                          description=desc, seniority=sen)

    def test_scores_bounded_and_relevant_beats_irrelevant(self):
        relevant = self._job("Credit Risk Analyst",
                             "Build PD scorecards with WoE and logistic regression, IFRS 9, Python, SQL")
        weak = self._job("Data Entry Clerk", "Type data into spreadsheets")
        scored = HeuristicScorer(self.s, self.cv).score_all([relevant, weak])
        by_title = {s.job.title: s for s in scored}
        for sc in scored:
            self.assertGreaterEqual(sc.score, 0)
            self.assertLessEqual(sc.score, 100)
        self.assertGreater(by_title["Credit Risk Analyst"].score,
                           by_title["Data Entry Clerk"].score)

    def test_matched_skills_and_reasons_present(self):
        job = self._job("Credit Risk Analyst",
                        "PD scorecard, WoE, logistic regression, python, sql, ifrs 9")
        sc = HeuristicScorer(self.s, self.cv).score_all([job])[0]
        self.assertIn("credit risk", sc.matched_skills)
        self.assertTrue(sc.reasons)

    def test_focus_boosts_modelling_over_generic_same_description(self):
        # Identical description; only the title differs. The scarce modelling role
        # must outrank a generic low-fit title thanks to the focus adjustment.
        # (AML/KYC are NO LONGER de-prioritised as of 2026-07-04 — they're a real
        # target track now — so use a still-deprioritised title here: credit control.)
        desc = "Credit risk, python, sql, portfolio monitoring for a bank."
        modelling = self._job("Credit Risk Modelling Analyst", desc)
        generic = self._job("Credit Control Analyst", desc)
        by = {s.job.title: s for s in HeuristicScorer(self.s, self.cv).score_all([modelling, generic])}
        self.assertGreater(by["Credit Risk Modelling Analyst"].score, by["Credit Control Analyst"].score)
        self.assertTrue(any("Priority" in r for r in by["Credit Risk Modelling Analyst"].reasons))
        self.assertTrue(any("De-prioritised" in r for r in by["Credit Control Analyst"].reasons))


class LLMParseTests(unittest.TestCase):
    def test_parses_json_amid_prose(self):
        text = 'Sure!\n{"fit_score": 82, "verdict": "strong", "one_line_reason": "great"}\nThanks'
        out = parse_llm_json(text)
        self.assertEqual(out["fit_score"], 82)

    def test_returns_none_on_garbage(self):
        self.assertIsNone(parse_llm_json("no json here"))


if __name__ == "__main__":
    unittest.main()
