"""Golden tests for volatility and largest month-end fall."""

import json
import math
import unittest
from numbers import Real
from pathlib import Path

from engine.risk import largest_fall, volatility
from engine.series import CoverageError, MonthlySeries, SeriesError


_GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "risk.json"
with _GOLDEN_PATH.open(encoding="utf-8") as golden_file:
    _GOLDEN = json.load(golden_file)

_TOLERANCE = _GOLDEN["tolerance_abs"]
_POUNDS_TOLERANCE = _GOLDEN["tolerance_abs_pounds"]
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
}
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


def _build(definition):
    return MonthlySeries.from_pairs(
        definition["name"],
        definition["currency"],
        definition["basis"],
        definition["pairs"],
    )


class RiskGoldenTests(unittest.TestCase):
    def assert_number_equal(self, actual, expected, tolerance):
        self.assertIsInstance(actual, Real)
        self.assertNotIsInstance(actual, bool)
        self.assertTrue(math.isfinite(actual))
        self.assertAlmostEqual(actual, expected, delta=tolerance)

    def assert_exact_value(self, actual, expected):
        if expected is None:
            self.assertIsNone(actual)
            return
        if isinstance(expected, bool):
            self.assertIs(type(actual), bool)
            self.assertIs(actual, expected)
            return
        if isinstance(expected, int):
            self.assertIs(type(actual), int)
            self.assertEqual(actual, expected)
            return
        if isinstance(expected, str):
            self.assertIs(type(actual), str)
            self.assertEqual(actual, expected)
            return
        self.fail("Unsupported exact comparison type: {}".format(type(expected).__name__))

    def assert_exact_error(self, case, callable_under_test):
        error_name = case["expected_error"]
        if error_name not in _ERRORS:
            self.fail("Unsupported expected error type: {}".format(error_name))
        expected_type = _ERRORS[error_name]
        with self.assertRaises(expected_type) as raised:
            callable_under_test()
        self.assertIs(type(raised.exception), expected_type)

    def assert_largest_fall_equal(self, actual, expected):
        self.assertEqual(set(actual), _LARGEST_FALL_KEYS)
        self.assertEqual(set(expected), _LARGEST_FALL_KEYS)
        for key, expected_value in expected.items():
            actual_value = actual[key]
            if isinstance(expected_value, float):
                tolerance = _POUNDS_TOLERANCE if key in _POUNDS_KEYS else _TOLERANCE
                self.assert_number_equal(actual_value, expected_value, tolerance)
            else:
                self.assert_exact_value(actual_value, expected_value)

    def exercise_case(self, case):
        series = _build(_GOLDEN["series"][case["series"]])
        check = case["check"]

        if check == "volatility":
            calculate = lambda: volatility(series)
            if "expected_error" in case:
                self.assert_exact_error(case, calculate)
            else:
                self.assert_number_equal(calculate(), case["expected"], _TOLERANCE)
            return

        if check == "largest_fall":
            calculate = lambda: largest_fall(series)
            if "expected_error" in case:
                self.assert_exact_error(case, calculate)
            else:
                self.assert_largest_fall_equal(calculate(), case["expected"])
            return

        self.fail("Unsupported golden check type: {}".format(check))


def _make_golden_test(case):
    def test(self):
        self.exercise_case(case)

    test.__name__ = "test_{}_{}".format(case["id"], case["check"])
    test.__doc__ = "Exercise golden case {}.".format(case["id"])
    return test


for _case in _GOLDEN["cases"]:
    _test_name = "test_{}_{}".format(_case["id"], _case["check"])
    setattr(RiskGoldenTests, _test_name, _make_golden_test(_case))


if __name__ == "__main__":
    unittest.main()
