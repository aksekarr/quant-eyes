"""Golden runner and command tests using temporary files and in-memory fetches."""

from copy import deepcopy
import datetime
import importlib.util
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engine.output import analyse
from pipeline.monthly import build_monthly_series, last_complete_month
from pipeline.providers import ProviderError
from pipeline.publish import PublishError, build_document, check_document
from pipeline.runner import RunError, run
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("runner.json")
_ERRORS = {"RunError": RunError, "ValueError": ValueError}
_FETCH_ERRORS = {"ProviderError": ProviderError, "RuntimeError": RuntimeError}
_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_data.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("build_data_under_test", _SCRIPT_PATH)
_BUILD_DATA = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(_BUILD_DATA)


def _expected_documents(case, registry, rows, today):
    """Compose expected files through the already-tested calculation modules."""
    names = case.get("expected_documents", [])
    if not names:
        return {}
    as_of = last_complete_month(today)

    def series(item):
        data = item["data"]
        return build_monthly_series(
            item["label"], data["currency"], data["basis"],
            deepcopy(rows[data["symbol"]]), as_of, data["start"],
        )

    fx = series(registry["fx"])
    benchmark = next(
        item for item in registry["instruments"] if item["role"] == "benchmark"
    )
    tracker = series(benchmark)
    documents = {}
    for instrument in registry["instruments"]:
        filename = instrument["id"] + ".json"
        if filename not in names:
            continue
        asset = series(instrument)
        results = analyse(
            asset, tracker, fx if instrument["data"]["currency"] == "USD" else None
        )
        document = build_document(registry, instrument["id"], results, as_of, today)
        documents[filename] = (
            json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    return documents


class RunnerGoldenTests(unittest.TestCase):
    def _prepare_output(self, out_dir, before_files):
        out_dir.mkdir(parents=True)
        for name, contents in before_files.items():
            path = out_dir / name
            if isinstance(contents, dict) and contents.get("folder") is True:
                path.mkdir()
            else:
                path.write_text(contents, encoding="utf-8")

    def _assert_files(self, case, out_dir, documents):
        if "expected_files" not in case:
            if case.get("out_dir_missing"):
                self.assertFalse(out_dir.exists())
            return
        expected = case["expected_files"]
        if expected is None:
            self.assertFalse(out_dir.exists())
            return
        self.assertTrue(out_dir.is_dir())
        self.assertEqual(sorted(path.name for path in out_dir.iterdir()), sorted(expected))
        self.assertEqual(set(documents), set(case.get("expected_documents", [])))
        for name in expected:
            path = out_dir / name
            if name in documents:
                self.assertEqual(path.read_text(encoding="utf-8"), documents[name])
            else:
                contents = case["before_files"][name]
                if isinstance(contents, dict) and contents.get("folder") is True:
                    self.assertTrue(path.is_dir())
                    self.assertEqual(list(path.iterdir()), [])
                else:
                    self.assertEqual(path.read_text(encoding="utf-8"), contents)

    def _assert_canaries(self, rows, out_dir, stdout):
        outputs = [("out", stdout)]
        if out_dir.exists():
            outputs.extend(
                (str(path.relative_to(out_dir)), path.read_text(encoding="utf-8"))
                for path in out_dir.rglob("*") if path.is_file()
            )
        for symbol_rows in rows.values():
            for _, value in symbol_rows:
                canary = value if isinstance(value, str) else repr(value)
                for name, text in outputs:
                    self.assertFalse(canary in text, "Raw row value leaked into " + name)

    def _exercise_run(self, case, registry, today, out_dir, fetch):
        def calculate():
            try:
                if "read_back_failure" in case:
                    failure = case["read_back_failure"]
                    calls = 0

                    def check_read_back(document, registry):
                        nonlocal calls
                        calls += 1
                        if calls == failure["call"]:
                            raise PublishError(failure["message"])
                        return check_document(document, registry)

                    with patch("pipeline.runner.check_document", side_effect=check_read_back):
                        return run(registry, fetch, today, out_dir)
                return run(registry, fetch, today, out_dir)
            except Exception as error:
                if "message_equals" in case:
                    self.assertEqual(str(error), case["message_equals"])
                raise

        if "expected_error" in case:
            assert_exact_error(self, case, calculate, _ERRORS)
        else:
            summary = calculate()
            if "expected_summary" in case:
                assert_result_equal(self, summary, case["expected_summary"], tolerance=0)
        return ""

    def _exercise_cli(self, case, registry, today, root, fetch):
        registry_path = root / "pipeline" / "instruments.json"
        registry_path.parent.mkdir()
        registry_path.write_text(
            case.get("registry_text", json.dumps(registry)), encoding="utf-8"
        )
        keys_calls = []

        def make_fetch(keys):
            keys_calls.append(deepcopy(keys))
            if "make_fetch_raises" in case:
                raise RuntimeError(case["make_fetch_raises"])
            return fetch

        out = StringIO()
        exit_code = _BUILD_DATA.main(
            deepcopy(case["argv"]), deepcopy(case["environ"]),
            today, out, root, make_fetch,
        )
        assert_result_equal(self, exit_code, case["expected_exit"], tolerance=0)
        stdout = out.getvalue()
        self.assertEqual(stdout, "".join(line + "\n" for line in case["expected_stdout"]))
        expected_keys = case["expected_keys"]
        assert_result_equal(
            self, keys_calls, [] if expected_keys is None else [expected_keys], tolerance=0
        )
        for required_text in case.get("message_must_contain", []):
            self.assertIn(required_text, stdout)
        for forbidden_text in case.get("message_must_not_contain", []):
            self.assertNotIn(forbidden_text, stdout)
        return stdout

    def exercise_case(self, case):
        registry = apply_edits(_GOLDEN["registry"], case.get("registry_edits", []))
        rows = apply_edits(_GOLDEN["rows"], case.get("rows_edits", []))
        if "today_datetime" in case:
            today = datetime.datetime.fromisoformat(case["today_datetime"])
        else:
            today = datetime.date.fromisoformat(case["today"])
        documents = _expected_documents(case, registry, rows, today)
        fetch_calls = []

        def fetch(data, as_of_month):
            symbol = data["symbol"]
            fetch_calls.append(symbol)
            failure = case.get("fetch_failures", {}).get(symbol)
            if failure is not None:
                raise _FETCH_ERRORS[failure["raise"]](failure["message"])
            return deepcopy(rows[symbol])

        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            out_dir = root / "data" / "derived"
            if case["check"] == "run":
                if not case.get("out_dir_missing"):
                    self._prepare_output(out_dir, case.get("before_files", {}))
                stdout = self._exercise_run(case, registry, today, out_dir, fetch)
            elif case["check"] == "cli":
                if "before_files" in case:
                    self._prepare_output(out_dir, case["before_files"])
                stdout = self._exercise_cli(case, registry, today, root, fetch)
            else:
                self.fail("Unsupported golden check type: {}".format(case["check"]))
            if "expected_fetch_order" in case:
                assert_result_equal(
                    self, fetch_calls, case["expected_fetch_order"], tolerance=0
                )
            self._assert_files(case, out_dir, documents)
            self._assert_canaries(rows, out_dir, stdout)


generate_golden_tests(RunnerGoldenTests, _GOLDEN["cases"], {"run", "cli"})


if __name__ == "__main__":
    unittest.main()
