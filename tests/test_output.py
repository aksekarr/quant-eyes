"""Golden and boundary tests for the single engine output."""

import unittest
from unittest.mock import patch

from engine.output import METHOD_VERSION, OutputError, analyse, check_output
from engine.series import CoverageError, MonthlySeries, SeriesError
from golden_support import (
    POUNDS_TOLERANCE_KEYS,
    assert_exact_error,
    assert_result_equal,
    build_series,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("output.json")
_TOLERANCE = _GOLDEN["tolerance_abs"]
_POUNDS_TOLERANCE = _GOLDEN["tolerance_abs_pounds"]
_ERRORS = {
    "OutputError": OutputError,
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
    "ValueError": ValueError,
}


class OutputGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        check = case["check"]
        if check == "analyse":
            asset = build_series(_GOLDEN["series"][case["asset"]])
            tracker = build_series(_GOLDEN["series"][case["tracker"]])
            fx_name = case.get("fx")
            fx = None if fx_name is None else build_series(_GOLDEN["series"][fx_name])
            calculate = lambda: analyse(asset, tracker, fx)
            expected = case.get("expected")
        elif check == "check_output":
            calculate = lambda: check_output(case["value"])
            if "expected_error" not in case:
                assert_result_equal(self, case["expected"], "accepted", _TOLERANCE)
            expected = None
        else:
            self.fail("Unsupported golden check type: {}".format(check))

        if "expected_error" in case:
            assert_exact_error(self, case, calculate, _ERRORS)
        else:
            assert_result_equal(
                self,
                calculate(),
                expected,
                _TOLERANCE,
                POUNDS_TOLERANCE_KEYS,
                _POUNDS_TOLERANCE,
            )


generate_golden_tests(OutputGoldenTests, _GOLDEN["cases"], {"analyse", "check_output"})


class OutputBoundaryTests(unittest.TestCase):
    def test_method_version(self):
        assert_result_equal(self, METHOD_VERSION, "1.0", _TOLERANCE)

    def test_nan_is_refused_inside_a_stress_window(self):
        value = {"stress_windows": [{}, {}, {"return": float("nan")}]}
        assert_exact_error(
            self, {"expected_error": "OutputError"}, lambda: check_output(value), _ERRORS
        )

    def test_infinity_is_refused(self):
        for infinite in (float("inf"), float("-inf")):
            with self.subTest(sign="positive" if infinite > 0 else "negative"):
                assert_exact_error(
                    self,
                    {"expected_error": "OutputError"},
                    lambda: check_output({"value": infinite}),
                    _ERRORS,
                )

    def test_tuple_is_refused(self):
        assert_exact_error(
            self,
            {"expected_error": "OutputError"},
            lambda: check_output({"nested": {"values": (1, 2)}}),
            _ERRORS,
        )

    def test_non_string_key_is_refused(self):
        assert_exact_error(
            self,
            {"expected_error": "OutputError"},
            lambda: check_output({"nested": {1: "text"}}),
            _ERRORS,
        )

    def test_short_history_keeps_covered_parts(self):
        series = MonthlySeries.from_pairs(
            "Short history", "GBP", "total_return",
            [("2020-01", 100), ("2020-02", 110)],
        )
        result = analyse(series, series)
        for profile in (result["own"], result["side_by_side"]["asset"],
                        result["side_by_side"]["tracker"]):
            # Two month-ends span one month: no yearly return or holding period,
            # and only one monthly return, too few for sample volatility.
            assert_result_equal(
                self,
                {key: profile[key] for key in (
                    "start", "end", "annualised_return", "volatility", "holding_periods"
                )},
                {
                    "start": "2020-01", "end": "2020-02",
                    "annualised_return": None, "volatility": None,
                    "holding_periods": {"1_year": None, "3_years": None, "5_years": None},
                },
                _TOLERANCE,
            )
            self.assertIsInstance(profile["largest_fall"], dict)
        for key in ("correlation", "rolling_correlation_36", "blend_90_10"):
            assert_result_equal(self, result["side_by_side"][key], None, _TOLERANCE)

    def test_no_common_months_keeps_own_profile(self):
        asset = build_series(_GOLDEN["series"]["UK_asset"])
        tracker = MonthlySeries.from_pairs(
            "Later tracker", "GBP", "total_return",
            [("2022-01", 100), ("2022-02", 110)],
        )
        pound_case = next(case for case in _GOLDEN["cases"] if case["id"] == "A02")
        expected = dict(pound_case["expected"], side_by_side=None)
        assert_result_equal(
            self, analyse(asset, tracker), expected, _TOLERANCE,
            POUNDS_TOLERANCE_KEYS, _POUNDS_TOLERANCE,
        )

    def test_undefined_correlation_propagates(self):
        series = MonthlySeries.from_pairs(
            "Constant history", "GBP", "total_return",
            [("2020-01", 100), ("2020-02", 100),
             ("2020-03", 100), ("2020-04", 100)],
        )
        assert_exact_error(
            self, {"expected_error": "SeriesError"},
            lambda: analyse(series, series), _ERRORS,
        )

    def test_labels_are_checked_before_fx_argument(self):
        cases = (
            ("US_asset", "Tracker_usd", None),
            ("US_asset_price", "Tracker", None),
            ("EUR_asset", "Tracker", "FX"),
        )
        for asset_name, tracker_name, fx_name in cases:
            with self.subTest(asset=asset_name, tracker=tracker_name):
                asset = build_series(_GOLDEN["series"][asset_name])
                tracker = build_series(_GOLDEN["series"][tracker_name])
                fx = None if fx_name is None else build_series(_GOLDEN["series"][fx_name])
                assert_exact_error(
                    self, {"expected_error": "SeriesError"},
                    lambda: analyse(asset, tracker, fx), _ERRORS,
                )

    def test_invalid_fx_labels_propagate(self):
        asset = build_series(_GOLDEN["series"]["US_asset"])
        tracker = build_series(_GOLDEN["series"]["Tracker"])
        assert_exact_error(
            self, {"expected_error": "SeriesError"},
            lambda: analyse(asset, tracker, tracker), _ERRORS,
        )

    def test_analyse_checks_its_result(self):
        asset = build_series(_GOLDEN["series"]["UK_asset"])
        tracker = build_series(_GOLDEN["series"]["Tracker"])
        with patch("engine.output.volatility", return_value=float("nan")):
            assert_exact_error(
                self, {"expected_error": "OutputError"},
                lambda: analyse(asset, tracker), _ERRORS,
            )


if __name__ == "__main__":
    unittest.main()
