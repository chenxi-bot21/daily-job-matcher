"""
Cross-run de-duplication: remember which jobs were already surfaced so daily
runs don't show the same posting twice.

Stored as a JSON list of job ids (most-recent last), capped so the file can't
grow without bound.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_KEEP_LAST = 5000
_KEY_RE = re.compile(r"[^a-z0-9]+")


def content_key(company: str, title: str) -> str:
    """A stable id for "the same job" independent of the posting's board id.

    LinkedIn re-posts an unchanged role under a *new* job id, so id-only history
    lets reposts slip back into the digest. Keying on normalised company+title
    catches those. Collision-safe with raw ids (this always contains a ``|``).
    """
    c = _KEY_RE.sub(" ", (company or "").lower()).strip()
    t = _KEY_RE.sub(" ", (title or "").lower()).strip()
    return f"{c}|{t}"


def _load_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [str(x) for x in data] if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError, OSError):
        return []


def load_seen(path: str | Path) -> set[str]:
    """Return the set of job ids already surfaced in earlier runs."""
    return set(_load_list(Path(path)))


def record_seen(path: str | Path, ids) -> None:
    """Append *ids* to the history (de-duplicated, order-preserving, capped)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = _load_list(path)
    seen = set(previous)
    combined = previous + [i for i in ids if i and i not in seen]
    path.write_text(json.dumps(combined[-_KEEP_LAST:]), encoding="utf-8")
