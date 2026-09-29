"""Golden tests for page data and the landing page's asset list."""

import unittest

from words.cards import WordsError, build_cards
from words.cards_567 import build_cards_567
from words.page import build_index, build_page, check_context
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("page.json")
_ERRORS = {"WordsError": WordsError}


class PageGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        check = case["check"]
        if check == "check_context":
            registry = apply_edits(_GOLDEN["registry"], case.get("registry_edits", []))
            context = apply_edits(
                _GOLDEN["contexts"][case["context"]],
                case.get("context_edits", []),
            )
            calculate = lambda: check_context(context, registry)
        elif check == "build_page":
            document = apply_edits(
                _GOLDEN["documents"][case["document"]],
                case.get("document_edits", []),
            )
            facts = case["facts"]
            calculate = lambda: build_page(document, facts)
        elif check == "build_index":
            registry = apply_edits(_GOLDEN["registry"], case.get("registry_edits", []))
            pages = []
            for entry in case["pages"]:
                document = apply_edits(_GOLDEN["documents"][entry["document"]], [])
                page = build_page(document, entry["facts"])
                pages.append(apply_edits(page, entry["page_edits"]))
            calculate = lambda: build_index(registry, pages)
        else:
            self.fail("Unsupported golden check type: {}".format(check))

        if "expected_error" in case:
            assert_exact_error(self, case, calculate, _ERRORS)
            return

        actual = calculate()
        if check == "check_context":
            self.assertEqual(case["expected"], "valid")
            expected = None
        elif check == "build_page":
            expected = apply_edits(case["expected_page"], [])
            first_cards = build_cards(document)
            later_cards = build_cards_567(document, facts)
            for field in ("cards", "claims"):
                expected[field] = first_cards[field] + later_cards[field]
            self.assertEqual(
                [card["id"] for card in actual["cards"]],
                ["bumpy", "worst", "panic", "next", "pound", "limits"],
            )
        else:
            expected = case["expected"]
        assert_result_equal(self, actual, expected, tolerance=0)


generate_golden_tests(
    PageGoldenTests,
    _GOLDEN["cases"],
    {"check_context", "build_page", "build_index"},
)


if __name__ == "__main__":
    unittest.main()
