"""Golden tests for stress windows and holding periods."""

import json
import math
import unittest
from numbers import Real
from pathlib import Path

from engine.series import CoverageError, MonthlySeries, SeriesError
from engine.windows import STRESS_WINDOWS, holding_periods, stress_windows


_GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "windows.json"
with _GOLDEN_PATH.open(encoding="utf-8") as golden_file:
    _GOLDEN = json.load(golden_file)

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


def _build(definition):
    return MonthlySeries.from_pairs(
        definition["name"],
        definition["currency"],
        definition["basis"],
        definition["pairs"],
    )


class WindowsGoldenTests(unittest.TestCase):
    def assert_number_equal(self, actual, expected):
        self.assertIsInstance(actual, Real)
        self.assertNotIsInstance(actual, bool)
        self.assertTrue(math.isfinite(actual))
        self.assertAlmostEqual(actual, expected, delta=_TOLERANCE)

    def assert_golden_value(self, actual, expected):
        if expected is None:
            self.assertIsNone(actual)
            return
        if type(expected) is bool:
            self.assertIs(type(actual), bool)
            self.assertIs(actual, expected)
            return
        if type(expected) is int:
            self.assertIs(type(actual), int)
            self.assertEqual(actual, expected)
            return
        if type(expected) is str:
            self.assertIs(type(actual), str)
            self.assertEqual(actual, expected)
            return
        if isinstance(expected, Real):
            self.assert_number_equal(actual, expected)
            return
        self.fail("Unsupported comparison type: {}".format(type(expected).__name__))

    def assert_exact_error(self, case, callable_under_test):
        error_name = case["expected_error"]
        if error_name not in _ERRORS:
            self.fail("Unsupported expected error type: {}".format(error_name))
        expected_type = _ERRORS[error_name]
        with self.assertRaises(expected_type) as raised:
            callable_under_test()
        self.assertIs(type(raised.exception), expected_type)

    def assert_stress_windows_equal(self, actual, expected):
        self.assertIs(type(actual), list)
        self.assertEqual(len(actual), len(expected))
        for actual_window, expected_window in zip(actual, expected):
            self.assertEqual(set(actual_window), _STRESS_KEYS)
            self.assertEqual(set(expected_window), _STRESS_KEYS)
            for key, expected_value in expected_window.items():
                self.assert_golden_value(actual_window[key], expected_value)

    def assert_holding_periods_equal(self, actual, expected):
        self.assertEqual(set(actual), _HOLDING_KEYS)
        self.assertEqual(set(expected), _HOLDING_KEYS)
        for key, expected_value in expected.items():
            self.assert_golden_value(actual[key], expected_value)

    def exercise_case(self, case):
        series = _build(_GOLDEN["series"][case["series"]])
        check = case["check"]

        if check == "stress_windows":
            calculate = lambda: stress_windows(series)
            if "expected_error" in case:
                self.assert_exact_error(case, calculate)
            else:
                self.assert_stress_windows_equal(calculate(), case["expected"])
            return

        if check == "holding_periods":
            calculate = lambda: holding_periods(series, case["months"])
            if "expected_error" in case:
                self.assert_exact_error(case, calculate)
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


def _make_golden_test(case):
    def test(self):
        self.exercise_case(case)

    test.__name__ = "test_{}_{}".format(case["id"], case["check"])
    test.__doc__ = "Exercise golden case {}.".format(case["id"])
    return test


for _case in _GOLDEN["cases"]:
    _test_name = "test_{}_{}".format(_case["id"], _case["check"])
    setattr(WindowsGoldenTests, _test_name, _make_golden_test(_case))


if __name__ == "__main__":
    unittest.main()
