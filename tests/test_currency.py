"""Golden tests for US-dollar conversion and currency return decomposition."""

import unittest

from engine.currency import currency_split, to_gbp
from engine.series import CoverageError, SeriesError
from golden_support import (
    assert_exact_error,
    assert_numeric_equal,
    assert_series_equal,
    build_series,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("currency.json")
_TOLERANCE = _GOLDEN["tolerance_abs"]
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
    "ValueError": ValueError,
}


class CurrencyGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        check = case["check"]
        asset = build_series(_GOLDEN["series"][case["asset"]])
        fx = build_series(_GOLDEN["series"][case["fx"]])

        if check == "to_gbp":
            calculate = lambda: to_gbp(asset, fx)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_series_equal(self, calculate(), case["expected"], _TOLERANCE)
            return

        if check == "currency_split":
            calculate = lambda: currency_split(asset, fx, case["start"], case["end"])
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                actual = calculate()
                self.assertEqual(
                    set(actual),
                    {"local_return", "currency_return", "gbp_return"},
                )
                for key, expected_value in case["expected"].items():
                    assert_numeric_equal(self, actual[key], expected_value, _TOLERANCE)
                self.assertAlmostEqual(
                    1.0 + actual["gbp_return"],
                    (1.0 + actual["local_return"]) * (1.0 + actual["currency_return"]),
                    delta=_TOLERANCE,
                )
            return

        self.fail("Unsupported golden check type: {}".format(check))


generate_golden_tests(
    CurrencyGoldenTests,
    _GOLDEN["cases"],
    {"to_gbp", "currency_split"},
)


if __name__ == "__main__":
    unittest.main()
