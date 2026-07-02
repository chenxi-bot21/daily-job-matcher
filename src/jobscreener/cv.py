"""
Load the CV and derive a lightweight skill profile.

Mirrors the workflow's *RetrieveCV → Extract from File → MapResume* steps:
read the CV file into plain text and label the skills it contains so the scorer
has a consistent representation to work with.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1024)
def _skill_re(skill: str) -> re.Pattern:
    # Word-boundary match so short tokens (r, pd, ead, var) don't match inside
    # other words ("lead", "read", "variable", "update").
    return re.compile(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", re.IGNORECASE)


def skill_present(text_lower: str, skill: str) -> bool:
    return _skill_re(skill).search(text_lower) is not None


@dataclass
class CVProfile:
    text: str
    skills: list[str]          # skills from the taxonomy found in the CV

    @property
    def text_lower(self) -> str:
        return self.text.lower()


def read_cv_text(path: str | Path) -> str:
    """Read a CV from .md/.txt or .docx (PDF supported if pypdf is installed)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"CV not found at {path}. Set JOBSCREENER_CV or --cv to your CV file."
        )
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(str(path)).paragraphs if p.text.strip())
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install pypdf to read PDF CVs, or use .docx/.md/.txt.") from exc
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    raise ValueError(f"Unsupported CV format: {suffix!r}. Use .md/.txt/.docx/.pdf.")


def build_cv_profile(text: str, skill_taxonomy: list[str]) -> CVProfile:
    """Label which taxonomy skills appear in the CV text."""
    low = text.lower()
    found = [s for s in skill_taxonomy if skill_present(low, s)]
    return CVProfile(text=text, skills=found)


def load_cv(path: str | Path, skill_taxonomy: list[str]) -> CVProfile:
    return build_cv_profile(read_cv_text(path), skill_taxonomy)
