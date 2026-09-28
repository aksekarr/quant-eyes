"""Golden tests for stress windows and holding periods."""

import unittest

from engine.series import CoverageError, SeriesError
from engine.windows import STRESS_WINDOWS, holding_periods, stress_windows
from golden_support import (
    assert_exact_error,
    assert_result_equal,
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


class WindowsGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        series = build_series(_GOLDEN["series"][case["series"]])
        check = case["check"]

        if check == "stress_windows":
            calculate = lambda: stress_windows(series)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_result_equal(
                    self, calculate(), case["expected"], _TOLERANCE
                )
            return

        if check == "holding_periods":
            calculate = lambda: holding_periods(series, case["months"])
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_result_equal(
                    self, calculate(), case["expected"], _TOLERANCE
                )
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
