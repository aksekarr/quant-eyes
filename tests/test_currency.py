"""Golden tests for US-dollar conversion and currency return decomposition."""

import json
import math
import unittest
from pathlib import Path

from engine.currency import currency_split, to_gbp
from engine.series import CoverageError, MonthlySeries, SeriesError


_GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "currency.json"
with _GOLDEN_PATH.open(encoding="utf-8") as golden_file:
    _GOLDEN = json.load(golden_file)

_TOLERANCE = _GOLDEN["tolerance_abs"]
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
    "ValueError": ValueError,
}


def _build(definition):
    return MonthlySeries.from_pairs(
        definition["name"],
        definition["currency"],
        definition["basis"],
        definition["pairs"],
    )


class CurrencyGoldenTests(unittest.TestCase):
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

    def assert_exact_error(self, case, callable_under_test):
        expected_type = _ERRORS[case["expected_error"]]
        with self.assertRaises(expected_type) as raised:
            callable_under_test()
        self.assertIs(type(raised.exception), expected_type)

    def exercise_case(self, case):
        check = case["check"]
        asset = _build(_GOLDEN["series"][case["asset"]])
        fx = _build(_GOLDEN["series"][case["fx"]])

        if check == "to_gbp":
            calculate = lambda: to_gbp(asset, fx)
            if "expected_error" in case:
                self.assert_exact_error(case, calculate)
            else:
                self.assert_series_equal(calculate(), case["expected"])
            return

        if check == "currency_split":
            calculate = lambda: currency_split(asset, fx, case["start"], case["end"])
            if "expected_error" in case:
                self.assert_exact_error(case, calculate)
            else:
                actual = calculate()
                self.assertEqual(
                    set(actual),
                    {"local_return", "currency_return", "gbp_return"},
                )
                for key, expected_value in case["expected"].items():
                    self.assert_numeric_equal(actual[key], expected_value)
                self.assertAlmostEqual(
                    1.0 + actual["gbp_return"],
                    (1.0 + actual["local_return"]) * (1.0 + actual["currency_return"]),
                    delta=_TOLERANCE,
                )
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
    setattr(CurrencyGoldenTests, _test_name, _make_golden_test(_case))


if __name__ == "__main__":
    unittest.main()
