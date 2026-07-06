"""Send the daily report by email — the last step of the automated daily cycle.

Usage (from job_screener/):

    python scripts/send_daily_email.py output/daily_report_2026-07-03.md \
        [--subject "每日求职日报 2026-07-03"]

Loads SMTP settings from ``.env`` (JOBSCREENER_SMTP_HOST/PORT/USER/PASS,
JOBSCREENER_EMAIL_TO) and delivers the markdown report as a simple HTML email
via :func:`jobscreener.email_out.send_report`. Exits non-zero with a clear
message if SMTP isn't configured, so the caller can fall back to a Gmail draft.
"""
from __future__ import annotations

import argparse
import html
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from jobscreener.email_out import email_configured, send_report  # noqa: E402


def load_dotenv(path: pathlib.Path) -> None:
    """Minimal .env loader (KEY=VALUE lines; no quoting rules needed here)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def md_to_html(md: str) -> str:
    """Very small markdown→HTML good enough for an email client.

    Handles headings, tables, bold, links and paragraphs; everything else is
    passed through escaped. Avoids third-party deps so it runs anywhere.
    """
    import re

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
        return s

    out: list[str] = ["<div style='font-family:sans-serif;font-size:14px;line-height:1.5'>"]
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            # table block
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            out.append("<table border='1' cellpadding='6' style='border-collapse:collapse'>")
            for r, row in enumerate(rows):
                if r == 1:
                    continue  # separator row
                tag = "th" if r == 0 else "td"
                out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in row) + "</tr>")
            out.append("</table>")
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{min(level,4)}>{inline(line.lstrip('# '))}</h{min(level,4)}>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
        i += 1
    out.append("</div>")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Email the daily report (SMTP from .env).")
    p.add_argument("report", help="path to the markdown report to send")
    p.add_argument("--subject", default=None, help="email subject (default: report's first heading)")
    args = p.parse_args(argv)

    root = pathlib.Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    if not email_configured():
        print("SMTP not configured (JOBSCREENER_SMTP_HOST/USER/PASS missing in .env) — "
              "fall back to a Gmail draft.", file=sys.stderr)
        return 2

    md = pathlib.Path(args.report).read_text(encoding="utf-8")
    subject = args.subject or next(
        (l.lstrip("# ").strip() for l in md.splitlines() if l.startswith("#")),
        pathlib.Path(args.report).stem,
    )
    send_report(md_to_html(md), subject)
    print(f"Sent: {subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
