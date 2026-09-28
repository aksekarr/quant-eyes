"""Golden tests for instrument facts and published documents."""

import datetime
import json
from pathlib import Path
import unittest

from engine.output import OutputError
from pipeline.publish import (
    PublishError,
    RegistryError,
    build_document,
    check_document,
    check_registry,
)
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    edit_in_place,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("publish.json")
_ROOT = Path(__file__).resolve().parents[1]
_ERRORS = {
    "RegistryError": RegistryError,
    "PublishError": PublishError,
    "OutputError": OutputError,
    "ValueError": ValueError,
}


class PublishGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        check = case["check"]

        if check == "registry_file":
            with (_ROOT / case["registry_file"]).open(encoding="utf-8") as registry_file:
                registry = json.load(registry_file)
        else:
            registry = apply_edits(
                _GOLDEN["registries"][case["registry"]],
                case.get("registry_edits", []),
            )

        if check in ("check_registry", "registry_file"):
            calculate = lambda: check_registry(registry)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                self.assertEqual(case["expected"], "valid")
                self.assertIsNone(calculate())
            return

        if check == "check_document":
            document = apply_edits(
                _GOLDEN["documents"][case["document"]],
                case.get("document_edits", []),
            )
            if case.get("round_trip", False):
                document = json.loads(json.dumps(document))
            calculate = lambda: check_document(document, registry)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                self.assertEqual(case["expected"], "valid")
                self.assertIsNone(calculate())
            return

        if check in ("build_document", "document_independent"):
            results = apply_edits(
                _GOLDEN["results"][case["results"]],
                case.get("results_edits", []),
            )
            if "generated_on" in case:
                generated_on = datetime.date.fromisoformat(case["generated_on"])
            elif "generated_on_datetime" in case:
                generated_on = datetime.datetime.fromisoformat(
                    case["generated_on_datetime"]
                )
            else:
                generated_on = case["generated_on_raw"]
            calculate = lambda: build_document(
                registry, case["instrument_id"], results,
                case["as_of_month"], generated_on,
            )
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                actual = calculate()
                if check == "document_independent":
                    edit_in_place(registry, case["in_place_registry_edits"])
                assert_result_equal(
                    self, actual, _GOLDEN["documents"][case["expected_document"]],
                    tolerance=0,
                )
            return

        self.fail("Unsupported golden check type: {}".format(check))


generate_golden_tests(
    PublishGoldenTests,
    _GOLDEN["cases"],
    {
        "check_registry", "registry_file", "build_document", "check_document",
        "document_independent",
    },
)


if __name__ == "__main__":
    unittest.main()
