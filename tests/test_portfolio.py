"""Golden tests for correlation and blended-portfolio comparisons."""

import unittest

from engine.portfolio import blend_comparison, correlation, rolling_correlation
from engine.series import CoverageError, SeriesError
from golden_support import (
    POUNDS_TOLERANCE_KEYS,
    assert_exact_error,
    assert_numeric_equal,
    assert_result_equal,
    build_series,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("portfolio.json")
_TOLERANCE = _GOLDEN["tolerance_abs"]
_POUNDS_TOLERANCE = _GOLDEN["tolerance_abs_pounds"]
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
    "ValueError": ValueError,
}


class PortfolioGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        asset = build_series(_GOLDEN["series"][case["asset"]])
        tracker = build_series(_GOLDEN["series"][case["tracker"]])
        check = case["check"]

        if check == "correlation":
            calculate = lambda: correlation(asset, tracker)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_numeric_equal(self, calculate(), case["expected"], _TOLERANCE)
            return

        if check == "rolling_correlation":
            calculate = lambda: rolling_correlation(asset, tracker, case["months"])
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_result_equal(
                    self, calculate(), case["expected"], _TOLERANCE
                )
            return

        if check == "blend_comparison":
            calculate = lambda: blend_comparison(
                tracker, asset, case["asset_weight"]
            )
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_result_equal(
                    self,
                    calculate(),
                    case["expected"],
                    _TOLERANCE,
                    POUNDS_TOLERANCE_KEYS,
                    _POUNDS_TOLERANCE,
                )
            return

        self.fail("Unsupported golden check type: {}".format(check))


generate_golden_tests(
    PortfolioGoldenTests,
    _GOLDEN["cases"],
    {"correlation", "rolling_correlation", "blend_comparison"},
)


if __name__ == "__main__":
    unittest.main()
