import tempfile
import unittest
from pathlib import Path

from jobscreener import history


class HistoryTests(unittest.TestCase):
    def test_empty_when_missing(self):
        self.assertEqual(history.load_seen(Path("nope_does_not_exist.json")), set())

    def test_record_then_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "seen.json"
            history.record_seen(p, ["a", "b", "c"])
            self.assertEqual(history.load_seen(p), {"a", "b", "c"})

    def test_record_deduplicates_and_appends(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "seen.json"
            history.record_seen(p, ["a", "b"])
            history.record_seen(p, ["b", "c"])  # b already seen
            self.assertEqual(history.load_seen(p), {"a", "b", "c"})

    def test_ignores_blank_ids(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "seen.json"
            history.record_seen(p, ["a", "", None])
            self.assertEqual(history.load_seen(p), {"a"})

    def test_content_key_normalises_and_matches_reposts(self):
        base = history.content_key("Citi", "KYC Operations Analyst")
        # Case, spacing and punctuation differences collapse to the same key.
        self.assertEqual(base, history.content_key("  citi ", "KYC   Operations, Analyst!"))
        # A different title does not collide.
        self.assertNotEqual(base, history.content_key("Citi", "Data Analyst"))
        # Always contains the separator, so it can't collide with a raw board id.
        self.assertIn("|", history.content_key("A", "B"))


if __name__ == "__main__":
    unittest.main()
