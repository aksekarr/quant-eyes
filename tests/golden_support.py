"""Shared helpers for tests backed by golden JSON files."""

import json
import math
from numbers import Real
from pathlib import Path

from engine.series import MonthlySeries


_GOLDEN_DIRECTORY = Path(__file__).resolve().parent / "golden"
_SPECIAL_VALUES = {
    "NaN": float("nan"),
    "Infinity": float("inf"),
    "-Infinity": float("-inf"),
}


def load_golden(filename):
    """Load a named golden JSON file from the tests folder."""
    path = _GOLDEN_DIRECTORY / filename
    with path.open(encoding="utf-8") as golden_file:
        return json.load(golden_file)


def decode_pairs(pairs):
    """Decode named non-finite values in golden observation pairs."""
    return [[month, _SPECIAL_VALUES.get(value, value)] for month, value in pairs]


def build_series(definition):
    """Build a monthly series from a golden series definition."""
    return MonthlySeries.from_pairs(
        definition["name"],
        definition["currency"],
        definition["basis"],
        decode_pairs(definition["pairs"]),
    )


def assert_numeric_equal(test_case, actual, expected, tolerance):
    """Compare finite real numbers within an absolute tolerance."""
    test_case.assertIsInstance(actual, Real)
    test_case.assertNotIsInstance(actual, bool)
    test_case.assertTrue(math.isfinite(actual))
    test_case.assertAlmostEqual(actual, expected, delta=tolerance)


def assert_exact_value(test_case, actual, expected):
    """Compare a string, null, boolean, or integer with its exact type."""
    if expected is None:
        test_case.assertIsNone(actual)
        return
    if type(expected) is bool:
        test_case.assertIs(type(actual), bool)
        test_case.assertIs(actual, expected)
        return
    if type(expected) is int:
        test_case.assertIs(type(actual), int)
        test_case.assertEqual(actual, expected)
        return
    if type(expected) is str:
        test_case.assertIs(type(actual), str)
        test_case.assertEqual(actual, expected)
        return
    test_case.fail(
        "Unsupported exact comparison type: {}".format(type(expected).__name__)
    )


def assert_series_equal(test_case, actual, expected, tolerance):
    """Compare series labels exactly and values numerically."""
    assert_exact_value(test_case, actual.name, expected["name"])
    assert_exact_value(test_case, actual.currency, expected["currency"])
    assert_exact_value(test_case, actual.basis, expected["basis"])
    test_case.assertEqual(len(actual.months), len(expected["months"]))
    for actual_month, expected_month in zip(actual.months, expected["months"]):
        assert_exact_value(test_case, actual_month, expected_month)
    test_case.assertEqual(len(actual.values), len(expected["values"]))
    for actual_value, expected_value in zip(actual.values, expected["values"]):
        assert_numeric_equal(test_case, actual_value, expected_value, tolerance)
    if "first_month" in expected:
        assert_exact_value(test_case, actual.first_month, expected["first_month"])
    if "last_month" in expected:
        assert_exact_value(test_case, actual.last_month, expected["last_month"])


def assert_exact_error(test_case, case, callable_under_test, errors):
    """Assert the exact named error type and any message requirements."""
    error_name = case["expected_error"]
    if error_name not in errors:
        test_case.fail("Unsupported expected error type: {}".format(error_name))
    expected_type = errors[error_name]
    with test_case.assertRaises(expected_type) as raised:
        callable_under_test()
    test_case.assertIs(type(raised.exception), expected_type)
    message = str(raised.exception)
    for required_text in case.get("message_must_contain", []):
        test_case.assertIn(required_text, message)
    for forbidden_text in case.get("message_must_not_contain", []):
        test_case.assertNotIn(forbidden_text, message)


def generate_golden_tests(test_case_class, cases, supported_checks):
    """Add one test per golden case and reject unknown check types."""
    generated_case_ids = set()
    generated_test_names = set()

    for case in cases:
        case_id = case["id"]
        if case_id in generated_case_ids:
            raise ValueError("Duplicate golden case ID: {}.".format(case_id))

        test_name = "test_{}_{}".format(case_id, case["check"])
        if test_name in generated_test_names or hasattr(test_case_class, test_name):
            raise ValueError(
                "Generated test name already exists for golden case ID: {}.".format(
                    case_id
                )
            )

        generated_case_ids.add(case_id)
        generated_test_names.add(test_name)

    def make_test(case):
        def test(test_case):
            check = case["check"]
            if check not in supported_checks:
                test_case.fail("Unsupported golden check type: {}".format(check))
            test_case.exercise_case(case)

        test.__name__ = "test_{}_{}".format(case["id"], case["check"])
        test.__doc__ = "Exercise golden case {}.".format(case["id"])
        return test

    for case in cases:
        test_name = "test_{}_{}".format(case["id"], case["check"])
        setattr(test_case_class, test_name, make_test(case))

    return generated_case_ids
