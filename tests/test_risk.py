"""Golden tests for volatility and largest month-end fall."""

import unittest

from engine.risk import largest_fall, volatility
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


_GOLDEN = load_golden("risk.json")
_TOLERANCE = _GOLDEN["tolerance_abs"]
_POUNDS_TOLERANCE = _GOLDEN["tolerance_abs_pounds"]
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
}


class RiskGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        series = build_series(_GOLDEN["series"][case["series"]])
        check = case["check"]

        if check == "volatility":
            calculate = lambda: volatility(series)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_numeric_equal(self, calculate(), case["expected"], _TOLERANCE)
            return

        if check == "largest_fall":
            calculate = lambda: largest_fall(series)
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
    RiskGoldenTests,
    _GOLDEN["cases"],
    {"volatility", "largest_fall"},
)


if __name__ == "__main__":
    unittest.main()
