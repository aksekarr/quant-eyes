"""Golden tests for stress windows and holding periods."""

import unittest

from engine.series import CoverageError, SeriesError
from engine.windows import STRESS_WINDOWS, holding_periods, stress_windows
from golden_support import (
    assert_exact_error,
    assert_exact_value,
    assert_numeric_equal,
    build_series,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("windows.json")
_TOLERANCE = _GOLDEN["tolerance_abs"]
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
    "ValueError": ValueError,
}
_STRESS_KEYS = {"window", "start", "end", "covered", "return"}
_HOLDING_KEYS = {
    "horizon_months",
    "periods",
    "non_overlapping_periods",
    "first_start",
    "last_end",
    "worst",
    "worst_start",
    "worst_end",
    "median",
    "best",
    "best_start",
    "best_end",
    "periods_lost_money",
    "share_lost_money",
    "worst_annualised",
    "median_annualised",
    "best_annualised",
}
_HOLDING_NUMERIC_KEYS = {
    "worst",
    "median",
    "best",
    "share_lost_money",
    "worst_annualised",
    "median_annualised",
    "best_annualised",
}


class WindowsGoldenTests(unittest.TestCase):
    def assert_stress_windows_equal(self, actual, expected):
        self.assertIs(type(actual), list)
        self.assertEqual(len(actual), len(expected))
        for actual_window, expected_window in zip(actual, expected):
            self.assertEqual(set(actual_window), _STRESS_KEYS)
            self.assertEqual(set(expected_window), _STRESS_KEYS)
            for key, expected_value in expected_window.items():
                if key == "return" and expected_value is not None:
                    assert_numeric_equal(
                        self, actual_window[key], expected_value, _TOLERANCE
                    )
                else:
                    assert_exact_value(self, actual_window[key], expected_value)

    def assert_holding_periods_equal(self, actual, expected):
        self.assertEqual(set(actual), _HOLDING_KEYS)
        self.assertEqual(set(expected), _HOLDING_KEYS)
        for key, expected_value in expected.items():
            if key in _HOLDING_NUMERIC_KEYS:
                assert_numeric_equal(self, actual[key], expected_value, _TOLERANCE)
            else:
                assert_exact_value(self, actual[key], expected_value)

    def exercise_case(self, case):
        series = build_series(_GOLDEN["series"][case["series"]])
        check = case["check"]

        if check == "stress_windows":
            calculate = lambda: stress_windows(series)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                self.assert_stress_windows_equal(calculate(), case["expected"])
            return

        if check == "holding_periods":
            calculate = lambda: holding_periods(series, case["months"])
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                self.assert_holding_periods_equal(calculate(), case["expected"])
            return

        self.fail("Unsupported golden check type: {}".format(check))

    def test_stress_windows_constant(self):
        first_stress_case = next(
            case for case in _GOLDEN["cases"] if case["check"] == "stress_windows"
        )
        expected = tuple(
            (window["window"], window["start"], window["end"])
            for window in first_stress_case["expected"]
        )
        self.assertEqual(STRESS_WINDOWS, expected)


generate_golden_tests(
    WindowsGoldenTests,
    _GOLDEN["cases"],
    {"stress_windows", "holding_periods"},
)


if __name__ == "__main__":
    unittest.main()
