import unittest

from lego_db.core import escape_like_pattern, normalize_setnum, parse_modification_text


class CoreParserTests(unittest.TestCase):
    def test_parse_modification_text_full(self) -> None:
        plan = parse_modification_text(r"+123-4 -567 2>890-1 [a\]b]>42")
        self.assertTrue(plan.has_tokens)
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.add, ["123-4"])
        self.assertEqual(plan.remove, ["567"])
        self.assertEqual(plan.conditions, [("890-1", 2)])
        self.assertEqual(plan.notes, [("42", "a]b")])

    def test_parse_modification_text_malformed_gap(self) -> None:
        plan = parse_modification_text("abc +1")
        self.assertTrue(plan.has_tokens)
        self.assertTrue(plan.malformed)
        self.assertEqual(plan.add, ["1"])

    def test_parse_modification_text_empty(self) -> None:
        plan = parse_modification_text("")
        self.assertFalse(plan.has_tokens)
        self.assertTrue(plan.malformed)

    def test_normalize_setnum(self) -> None:
        self.assertEqual(normalize_setnum("1234-1"), "1234")
        self.assertEqual(normalize_setnum("1234"), "1234")
        self.assertEqual(normalize_setnum("abc"), "abc")

    def test_escape_like_pattern(self) -> None:
        self.assertEqual(escape_like_pattern(r"a\b_c%"), r"a\\b\_c\%")


if __name__ == "__main__":
    unittest.main()