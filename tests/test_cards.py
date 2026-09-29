"""Golden tests for displayed numbers, card text and their claims."""

import math
import unittest

from words.cards import (
    WordsError,
    build_cards,
    month_name,
    months_display,
    percent_display,
    pounds_display,
)
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("cards.json")
_ERRORS = {"WordsError": WordsError, "ValueError": ValueError}


class CardsGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        check = case["check"]
        if check == "percent_display":
            calculate = lambda: percent_display(case["value"])
        elif check == "pounds_display":
            calculate = lambda: pounds_display(case["value"])
        elif check == "months_display":
            calculate = lambda: months_display(case["n"])
        elif check == "month_name":
            calculate = lambda: month_name(case["month"])
        elif check == "build_cards":
            document = apply_edits(
                _GOLDEN["documents"][case["document"]],
                case.get("document_edits", []),
            )
            calculate = lambda: build_cards(document)
        else:
            self.fail("Unsupported golden check type: {}".format(check))

        if "expected_error" in case:
            assert_exact_error(self, case, calculate, _ERRORS)
            return

        actual = calculate()
        expected = case["expected"]
        assert_result_equal(self, actual, expected, tolerance=0)
        if check == "percent_display" and expected["points"] == 0.0:
            self.assertEqual(math.copysign(1, actual["points"]), 1)
        if check == "build_cards":
            for claim, expected_claim in zip(actual["claims"], expected["claims"]):
                if expected_claim["unit"] == "percent" and expected_claim["value"] == 0.0:
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
    CardsGoldenTests,
    _GOLDEN["cases"],
    {"percent_display", "pounds_display", "months_display", "month_name", "build_cards"},
)


if __name__ == "__main__":
    unittest.main()
