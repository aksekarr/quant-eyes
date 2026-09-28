"""Golden tests for correlation and blended-portfolio comparisons."""

import unittest

from engine.portfolio import blend_comparison, correlation, rolling_correlation
from engine.series import CoverageError, SeriesError
from golden_support import (
    assert_exact_error,
    assert_exact_value,
    assert_numeric_equal,
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
_ROLLING_KEYS = {"windows", "lowest", "lowest_end", "highest", "highest_end"}
_COMPARISON_KEYS = {
    "start",
    "end",
    "months",
    "asset_weight",
    "rebalance",
    "tracker",
    "blend",
}
_SUMMARY_KEYS = {"total_return", "annualised_return", "volatility", "largest_fall"}
_LARGEST_FALL_KEYS = {
    "max_drawdown",
    "peak_month",
    "trough_month",
    "recovery_month",
    "recovered",
    "months_peak_to_trough",
    "months_trough_to_recovery",
    "months_underwater",
    "ten_thousand_at_trough",
    "ten_thousand_lost",
    "drawdown_at_end",
}
_POUNDS_KEYS = {"ten_thousand_at_trough", "ten_thousand_lost"}
_FALL_NUMERIC_KEYS = _POUNDS_KEYS | {"max_drawdown", "drawdown_at_end"}


class PortfolioGoldenTests(unittest.TestCase):
    def assert_rolling_equal(self, actual, expected):
        self.assertEqual(set(actual), _ROLLING_KEYS)
        self.assertEqual(set(expected), _ROLLING_KEYS)
        for key, expected_value in expected.items():
            if key in {"lowest", "highest"}:
                assert_numeric_equal(self, actual[key], expected_value, _TOLERANCE)
            else:
                assert_exact_value(self, actual[key], expected_value)

    def assert_largest_fall_equal(self, actual, expected):
        self.assertEqual(set(actual), _LARGEST_FALL_KEYS)
        self.assertEqual(set(expected), _LARGEST_FALL_KEYS)
        for key, expected_value in expected.items():
            if key in _FALL_NUMERIC_KEYS:
                tolerance = _POUNDS_TOLERANCE if key in _POUNDS_KEYS else _TOLERANCE
                assert_numeric_equal(self, actual[key], expected_value, tolerance)
            else:
                assert_exact_value(self, actual[key], expected_value)

    def assert_summary_equal(self, actual, expected):
        self.assertEqual(set(actual), _SUMMARY_KEYS)
        self.assertEqual(set(expected), _SUMMARY_KEYS)
        for key, expected_value in expected.items():
            if key == "largest_fall":
                self.assert_largest_fall_equal(actual[key], expected_value)
            elif expected_value is None:
                assert_exact_value(self, actual[key], expected_value)
            else:
                assert_numeric_equal(self, actual[key], expected_value, _TOLERANCE)

    def assert_comparison_equal(self, actual, expected):
        self.assertEqual(set(actual), _COMPARISON_KEYS)
        self.assertEqual(set(expected), _COMPARISON_KEYS)
        for key, expected_value in expected.items():
            if key in {"tracker", "blend"}:
                self.assert_summary_equal(actual[key], expected_value)
            elif key == "asset_weight":
                assert_numeric_equal(self, actual[key], expected_value, _TOLERANCE)
            else:
                assert_exact_value(self, actual[key], expected_value)

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
                self.assert_rolling_equal(calculate(), case["expected"])
            return

        if check == "blend_comparison":
            calculate = lambda: blend_comparison(
                tracker, asset, case["asset_weight"]
            )
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                self.assert_comparison_equal(calculate(), case["expected"])
            return

        self.fail("Unsupported golden check type: {}".format(check))


generate_golden_tests(
    PortfolioGoldenTests,
    _GOLDEN["cases"],
    {"correlation", "rolling_correlation", "blend_comparison"},
)


if __name__ == "__main__":
    unittest.main()
