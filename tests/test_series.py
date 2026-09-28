"""Golden tests for monthly series validation and foundational returns."""

import unittest

from engine.series import (
    CoverageError,
    SeriesError,
    annualise,
    common_window,
    monthly_returns,
    period_return,
)
from golden_support import (
    assert_exact_error,
    assert_exact_value,
    assert_numeric_equal,
    assert_series_equal,
    build_series,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("foundation.json")
_TOLERANCE = _GOLDEN["tolerance_abs"]
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
    "ValueError": ValueError,
}


class FoundationGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        check = case["check"]

        if check == "series_properties":
            series = build_series(_GOLDEN["series"][case["series"]])
            assert_series_equal(self, series, case["expected"], _TOLERANCE)
            return

        if check == "monthly_returns":
            series = build_series(_GOLDEN["series"][case["series"]])
            actual = monthly_returns(series)
            self.assertEqual(len(actual), len(case["expected"]))
            for (actual_month, actual_return), (expected_month, expected_return) in zip(
                actual, case["expected"]
            ):
                assert_exact_value(self, actual_month, expected_month)
                assert_numeric_equal(self, actual_return, expected_return, _TOLERANCE)
            return

        if check == "period_return":
            series = build_series(_GOLDEN["series"][case["series"]])
            calculate = lambda: period_return(series, case["start"], case["end"])
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_numeric_equal(self, calculate(), case["expected"], _TOLERANCE)
            return

        if check == "annualise":
            calculate = lambda: annualise(case["total_return"], case["months"])
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_numeric_equal(self, calculate(), case["expected"], _TOLERANCE)
            return

        if check == "common_window":
            a = build_series(_GOLDEN["series"][case["a"]])
            b = build_series(_GOLDEN["series"][case["b"]])
            calculate = lambda: common_window(a, b)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                actual_a, actual_b = calculate()
                assert_series_equal(self, actual_a, case["expected_a"], _TOLERANCE)
                assert_series_equal(self, actual_b, case["expected_b"], _TOLERANCE)
            return

        if check == "invalid_series":
            assert_exact_error(self, case, lambda: build_series(case["build"]), _ERRORS)
            return

        self.fail("Unsupported golden check type: {}".format(check))

    def test_all_golden_case_ids_are_exercised(self):
        case_ids = [case["id"] for case in _GOLDEN["cases"]]
        self.assertEqual(len(case_ids), len(set(case_ids)), "Golden case IDs must be unique.")
        self.assertEqual(set(case_ids), _GENERATED_CASE_IDS)

    def test_series_is_immutable(self):
        series = build_series(_GOLDEN["series"]["S1"])
        with self.assertRaises(AttributeError):
            series.name = "Changed"
        with self.assertRaises(AttributeError):
            series._values = (1.0, 2.0)
        with self.assertRaises(TypeError):
            series.values[0] = 1.0


_GENERATED_CASE_IDS = generate_golden_tests(
    FoundationGoldenTests,
    _GOLDEN["cases"],
    {
        "series_properties",
        "monthly_returns",
        "period_return",
        "annualise",
        "common_window",
        "invalid_series",
    },
)


if __name__ == "__main__":
    unittest.main()
