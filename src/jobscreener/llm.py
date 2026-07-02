"""
Optional LLM re-scoring (the *OpenAI Chat Model → Structured Output Parser →
Parse LLM JSON* steps).

Claude re-scores the heuristic shortlist and returns a strict JSON verdict per
job. Running only on the shortlist keeps token cost bounded. If no API key is
set, the pipeline simply skips this stage and ranks on the heuristic score.
"""
from __future__ import annotations

import json
import re

from .config import Settings
from .cv import CVProfile
from .models import ScoredJob

_SYSTEM = ("You are an expert career coach screening job postings for a candidate. "
           "Be objective, strict, and concise. Consider skills, domain, and seniority fit.")

_PROMPT = (
    "Candidate CV:\n{cv}\n\n"
    "Job posting:\nTitle: {title}\nCompany: {company}\nLocation: {location}\n"
    "Description:\n{jd}\n\n"
    "Return ONLY a JSON object, no prose, with keys:\n"
    '{{"fit_score": <int 0-100>, "verdict": "strong|good|moderate|weak", '
    '"matched_strengths": [<up to 4 short strings>], "gaps": [<up to 3 short strings>], '
    '"one_line_reason": "<one sentence>"}}'
)


class Claude:
    def __init__(self, api_key: str, model: str):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int = 500) -> str:
        msg = self._client.messages.create(
            model=self._model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()


def parse_llm_json(text: str) -> dict | None:
    """Extract the first JSON object from the model's reply, tolerating stray prose."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _apply_verdict(scored: ScoredJob, verdict: dict) -> ScoredJob:
    fit = verdict.get("fit_score")
    if isinstance(fit, (int, float)):
        scored.score = round(max(0.0, min(100.0, float(fit))), 1)
    reasons = list(verdict.get("matched_strengths", []))
    if verdict.get("one_line_reason"):
        reasons.insert(0, verdict["one_line_reason"])
    if reasons:
        scored.reasons = reasons
    scored.llm_used = True
    return scored


def rescore_with_llm(shortlist: list[ScoredJob], cv: CVProfile, settings: Settings) -> list[ScoredJob]:
    """Re-score each shortlisted job with Claude; fall back to the heuristic on error."""
    client = Claude(settings.api_key, settings.model)
    for scored in shortlist:
        job = scored.job
        prompt = _PROMPT.format(cv=cv.text[:2500], title=job.title, company=job.company,
                                location=job.location, jd=job.description[:2000])
        try:
            verdict = parse_llm_json(client.complete(_SYSTEM, prompt))
        except Exception:  # network / API error -> keep heuristic score
            verdict = None
        if verdict:
            _apply_verdict(scored, verdict)
    return shortlist
