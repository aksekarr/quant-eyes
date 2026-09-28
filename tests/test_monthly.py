"""Golden tests for selecting provider month-end rows."""

import datetime
import unittest

from engine.series import CoverageError, SeriesError
from pipeline.monthly import (
    ProviderDataError,
    build_monthly_series,
    last_complete_month,
    month_end_pairs,
)
from golden_support import (
    assert_exact_error,
    assert_exact_value,
    assert_numeric_equal,
    assert_series_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("monthly.json")
_TOLERANCE = _GOLDEN["tolerance_abs"]
_ERRORS = {
    "ProviderDataError": ProviderDataError,
    "CoverageError": CoverageError,
    "SeriesError": SeriesError,
    "ValueError": ValueError,
}


class MonthlyGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        check = case["check"]

        if check == "last_complete_month":
            if "today" in case:
                today = datetime.date.fromisoformat(case["today"])
            elif "today_datetime" in case:
                today = datetime.datetime.fromisoformat(case["today_datetime"])
            else:
                today = case["today_raw"]
            calculate = lambda: last_complete_month(today)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_exact_value(self, calculate(), case["expected"])
            return

        # Provider values retain their JSON types, including numeric text.
        rows = _GOLDEN["rows"][case["rows"]]
        arguments = {"through": case["through"]}
        if "start" in case:
            arguments["start"] = case["start"]

        if check == "month_end_pairs":
            calculate = lambda: month_end_pairs(rows, **arguments)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                actual = calculate()
                self.assertIs(type(actual), list)
                self.assertEqual(len(actual), len(case["expected"]))
                for pair, (expected_month, expected_value) in zip(actual, case["expected"]):
                    self.assertIs(type(pair), tuple)
                    actual_month, actual_value = pair
                    assert_exact_value(self, actual_month, expected_month)
                    self.assertIs(type(actual_value), float)
                    assert_numeric_equal(self, actual_value, expected_value, _TOLERANCE)
            return

        if check == "build_monthly_series":
            calculate = lambda: build_monthly_series(
                case["name"], case["currency"], case["basis"], rows, **arguments
            )
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_series_equal(self, calculate(), case["expected"], _TOLERANCE)
            return

        self.fail("Unsupported golden check type: {}".format(check))


generate_golden_tests(
    MonthlyGoldenTests,
    _GOLDEN["cases"],
    {"last_complete_month", "month_end_pairs", "build_monthly_series"},
)


if __name__ == "__main__":
    unittest.main()
