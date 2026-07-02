"""
jobscreener — a daily AI job-screening pipeline.

A Python port of an n8n "morning job digest" workflow: load a CV, ingest fresh
job postings, normalise / de-duplicate / hard-filter them, score each posting
against the CV (heuristic + optional LLM), rank, take the top N, and render an
HTML report (optionally emailed).

Design goals: runs end-to-end offline with bundled sample postings and no API
key; upgrades transparently when a real job source and an Anthropic key are
configured. Pipeline stages mirror the original workflow — see
:mod:`jobscreener.pipeline`.
"""

__version__ = "1.0.0"
__author__ = "Chenxi Zhao"

__all__ = ["__version__", "__author__"]
