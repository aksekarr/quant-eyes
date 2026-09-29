"""Golden tests for cards 5 to 7, their displayed numbers and claims."""

import math
import unittest

from words.cards import WordsError
from words.cards_567 import (
    build_cards_567,
    correlation_display,
    signed_percent_display,
)
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("cards_567.json")
_ERRORS = {"WordsError": WordsError, "ValueError": ValueError}


class Cards567GoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        check = case["check"]
        if check == "correlation_display":
            calculate = lambda: correlation_display(case["value"])
        elif check == "signed_percent_display":
            calculate = lambda: signed_percent_display(case["value"])
        elif check == "build_cards_567":
            document = apply_edits(
                _GOLDEN["documents"][case["document"]],
                case.get("document_edits", []),
            )
            facts = apply_edits(case["facts"], case.get("facts_edits", []))
            calculate = lambda: build_cards_567(document, facts)
        else:
            self.fail("Unsupported golden check type: {}".format(check))

        if "expected_error" in case:
            assert_exact_error(self, case, calculate, _ERRORS)
            return

        actual = calculate()
        expected = case["expected"]
        assert_result_equal(self, actual, expected, tolerance=0)
        if check in ("correlation_display", "signed_percent_display"):
            value_key = "value" if check == "correlation_display" else "points"
            if expected[value_key] == 0.0:
                self.assertEqual(math.copysign(1, actual[value_key]), 1)
        if check == "build_cards_567":
            for claim, expected_claim in zip(actual["claims"], expected["claims"]):
                if expected_claim["value"] == 0.0:
                    self.assertEqual(math.copysign(1, claim["value"]), 1)
            self._check_claims(actual)

    def _check_claims(self, result):
        claim_ids = [claim["id"] for claim in result["claims"]]
        self.assertEqual(len(claim_ids), len(set(claim_ids)))
        claims_by_id = {claim["id"]: claim for claim in result["claims"]}
        used_claim_ids = set()
        for card in result["cards"]:
            for sentence in card["sentences"]:
                next_position = 0
                for claim_id in sentence["claims"]:
                    self.assertIn(claim_id, claims_by_id)
                    display = claims_by_id[claim_id]["display"]
                    position = sentence["text"].find(display, next_position)
                    self.assertGreaterEqual(position, next_position)
                    next_position = position + len(display)
                    used_claim_ids.add(claim_id)
        self.assertEqual(used_claim_ids, set(claim_ids))


generate_golden_tests(
    Cards567GoldenTests,
    _GOLDEN["cases"],
    {"correlation_display", "signed_percent_display", "build_cards_567"},
)


if __name__ == "__main__":
    unittest.main()
