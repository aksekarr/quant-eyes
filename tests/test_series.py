"""Golden tests for monthly series validation and foundational returns."""

import json
import math
import unittest
from pathlib import Path

from engine.series import (
    CoverageError,
    MonthlySeries,
    SeriesError,
    annualise,
    common_window,
    monthly_returns,
    period_return,
)


_GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "foundation.json"
with _GOLDEN_PATH.open(encoding="utf-8") as golden_file:
    _GOLDEN = json.load(golden_file)

_TOLERANCE = _GOLDEN["tolerance_abs"]
_SPECIAL_VALUES = {
    "NaN": float("nan"),
    "Infinity": float("inf"),
    "-Infinity": float("-inf"),
}
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
    "ValueError": ValueError,
}


def _decode_pairs(pairs):
    decoded = []
    for month, value in pairs:
        decoded.append([month, _SPECIAL_VALUES.get(value, value)])
    return decoded


def _build(definition):
    return MonthlySeries.from_pairs(
        definition["name"],
        definition["currency"],
        definition["basis"],
        _decode_pairs(definition["pairs"]),
    )


class FoundationGoldenTests(unittest.TestCase):
    def assert_numeric_equal(self, actual, expected):
        self.assertTrue(math.isfinite(actual))
        self.assertAlmostEqual(actual, expected, delta=_TOLERANCE)

    def assert_series_equal(self, actual, expected):
        self.assertEqual(actual.name, expected["name"])
        self.assertEqual(actual.currency, expected["currency"])
        self.assertEqual(actual.basis, expected["basis"])
        self.assertEqual(actual.months, tuple(expected["months"]))
        self.assertEqual(len(actual.values), len(expected["values"]))
        for actual_value, expected_value in zip(actual.values, expected["values"]):
            self.assert_numeric_equal(actual_value, expected_value)
        if "first_month" in expected:
            self.assertEqual(actual.first_month, expected["first_month"])
        if "last_month" in expected:
            self.assertEqual(actual.last_month, expected["last_month"])

    def assert_expected_error(self, case, callable_under_test):
        error_type = _ERRORS[case["expected_error"]]
        with self.assertRaises(error_type) as raised:
            callable_under_test()
        self.assertIs(type(raised.exception), error_type)
        message = str(raised.exception)
        for required_text in case.get("message_must_contain", []):
            self.assertIn(required_text, message)
        for forbidden_text in case.get("message_must_not_contain", []):
            self.assertNotIn(forbidden_text, message)

    def exercise_case(self, case):
        check = case["check"]

        if check == "series_properties":
            series = _build(_GOLDEN["series"][case["series"]])
            self.assert_series_equal(series, case["expected"])
            return

        if check == "monthly_returns":
            series = _build(_GOLDEN["series"][case["series"]])
            actual = monthly_returns(series)
            self.assertEqual(len(actual), len(case["expected"]))
            for (actual_month, actual_return), (expected_month, expected_return) in zip(
                actual, case["expected"]
            ):
                self.assertEqual(actual_month, expected_month)
                self.assert_numeric_equal(actual_return, expected_return)
            return

        if check == "period_return":
            series = _build(_GOLDEN["series"][case["series"]])
            calculate = lambda: period_return(series, case["start"], case["end"])
            if "expected_error" in case:
                self.assert_expected_error(case, calculate)
            else:
                self.assert_numeric_equal(calculate(), case["expected"])
            return

        if check == "annualise":
            calculate = lambda: annualise(case["total_return"], case["months"])
            if "expected_error" in case:
                self.assert_expected_error(case, calculate)
            else:
                self.assert_numeric_equal(calculate(), case["expected"])
            return

        if check == "common_window":
            a = _build(_GOLDEN["series"][case["a"]])
            b = _build(_GOLDEN["series"][case["b"]])
            calculate = lambda: common_window(a, b)
            if "expected_error" in case:
                self.assert_expected_error(case, calculate)
            else:
                actual_a, actual_b = calculate()
                self.assert_series_equal(actual_a, case["expected_a"])
                self.assert_series_equal(actual_b, case["expected_b"])
            return

        if check == "invalid_series":
            self.assert_expected_error(case, lambda: _build(case["build"]))
            return

        self.fail("Unsupported golden check type: {}".format(check))

    def test_all_golden_case_ids_are_exercised(self):
        case_ids = [case["id"] for case in _GOLDEN["cases"]]
        self.assertEqual(len(case_ids), len(set(case_ids)), "Golden case IDs must be unique.")
        self.assertEqual(set(case_ids), _GENERATED_CASE_IDS)

    def test_series_is_immutable(self):
        series = _build(_GOLDEN["series"]["S1"])
        with self.assertRaises(AttributeError):
            series.name = "Changed"
        with self.assertRaises(AttributeError):
            series._values = (1.0, 2.0)
        with self.assertRaises(TypeError):
            series.values[0] = 1.0


def _make_golden_test(case):
    def test(self):
        self.exercise_case(case)

    test.__name__ = "test_{}_{}".format(case["id"], case["check"])
    test.__doc__ = "Exercise golden case {}.".format(case["id"])
    return test


_GENERATED_CASE_IDS = set()
for _case in _GOLDEN["cases"]:
    _test_name = "test_{}_{}".format(_case["id"], _case["check"])
    setattr(FoundationGoldenTests, _test_name, _make_golden_test(_case))
    _GENERATED_CASE_IDS.add(_case["id"])


if __name__ == "__main__":
    unittest.main()
