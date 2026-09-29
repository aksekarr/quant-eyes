"""Golden tests for the section 15 headline checker."""

import unittest

from words.cards import WordsError
from words.headline import check_approvals, check_headline
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("headline.json")
_ERRORS = {"WordsError": WordsError}


class HeadlineGoldenTests(unittest.TestCase):
    def _assert_problems(self, actual, expected_rules):
        rules = []
        for problem in actual:
            self.assertIs(type(problem), str)
            self.assertIn(": ", problem)
            rule, detail = problem.split(": ", 1)
            self.assertTrue(rule)
            self.assertTrue(detail)
            if rule not in rules:
                rules.append(rule)
        self.assertEqual(rules, expected_rules)

    def exercise_case(self, case):
        registry = apply_edits(_GOLDEN["registry"], [])
        if case["check"] in ("check_headline", "word_list"):
            page = apply_edits(_GOLDEN["pages"][case["page"]], [])
            if case["check"] == "check_headline":
                self._assert_problems(
                    check_headline(case["text"], apply_edits(case["claims"], []), page, registry),
                    case["expected_rules"],
                )
            else:
                for word in _GOLDEN["word_lists"][case["list"]]:
                    with self.subTest(word=word):
                        self._assert_problems(
                            check_headline(
                                case["template"].replace("{word}", word),
                                apply_edits(case["claims"], []), page, registry,
                            ),
                            case["expected_rules"],
                        )
            return

        approvals = apply_edits(
            _GOLDEN["approvals"][case["approvals"]],
            case.get("approvals_edits", []),
        )
        pages = [apply_edits(_GOLDEN["pages"][name], []) for name in case["pages"]]
        calculate = lambda: check_approvals(approvals, pages, registry)
        if "expected_error" in case:
            assert_exact_error(self, case, calculate, _ERRORS)
            return
        actual = calculate()
        assert_result_equal(self, actual, case["expected"], tolerance=0)
        self.assertEqual(list(actual), list(case["expected"]))


generate_golden_tests(
    HeadlineGoldenTests,
    _GOLDEN["cases"],
    {"check_headline", "word_list", "check_approvals"},
)


if __name__ == "__main__":
    unittest.main()
