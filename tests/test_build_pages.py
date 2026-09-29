"""Golden page writer and command tests using only temporary folders."""

from contextlib import ExitStack
from copy import deepcopy
import importlib.util
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from words.cards import WordsError
from words.page import build_index, build_page
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("build_pages.json")
_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_pages.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("build_pages_under_test", _SCRIPT_PATH)
_BUILD_PAGES = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(_BUILD_PAGES)
_ERRORS = {"PageError": _BUILD_PAGES.PageError}
_PAGE_ERRORS = {"WordsError": WordsError, "RuntimeError": RuntimeError}


def _expected_pages(case, registry, context, documents):
    """Compose the expected files through the already-tested page builders."""
    names = case.get("expected_pages", [])
    if not names:
        return {}
    pages = []
    values = {}
    for instrument in registry["instruments"]:
        if instrument["role"] != "asset":
            continue
        instrument_id = instrument["id"]
        facts = {
            key: value for key, value in context["instruments"][instrument_id].items()
            if key != "why"
        }
        page = build_page(deepcopy(documents[instrument_id]), deepcopy(facts))
        pages.append(page)
        values[instrument_id + ".json"] = page
    values["index.json"] = build_index(deepcopy(registry), pages)
    return {
        name: json.dumps(
            values[name], indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False,
        ) + "\n"
        for name in names
    }


class BuildPagesGoldenTests(unittest.TestCase):
    def _prepare_output(self, out_dir, before_files):
        out_dir.mkdir(parents=True)
        for name, contents in before_files.items():
            path = out_dir / name
            if isinstance(contents, dict) and contents.get("folder") is True:
                path.mkdir()
            else:
                path.write_text(contents, encoding="utf-8")

    def _assert_files(self, case, out_dir, pages):
        expected = case["expected_files"]
        if expected is None:
            self.assertFalse(out_dir.exists())
            return
        self.assertTrue(out_dir.is_dir())
        assert_result_equal(
            self, sorted(path.name for path in out_dir.iterdir()),
            sorted(expected), tolerance=0,
        )
        self.assertEqual(set(pages), set(case.get("expected_pages", [])))
        for name in expected:
            path = out_dir / name
            if name in pages:
                self.assertEqual(path.read_bytes(), pages[name].encode("utf-8"))
            else:
                contents = case["before_files"][name]
                if isinstance(contents, dict) and contents.get("folder") is True:
                    self.assertTrue(path.is_dir())
                    self.assertEqual(list(path.iterdir()), [])
                else:
                    self.assertEqual(path.read_bytes(), contents.encode("utf-8"))

    def _patch_builders(self, case, patches):
        if "page_failure" in case or "read_back_mismatch" in case:
            calls = 0

            def build_page_for_case(document, facts):
                nonlocal calls
                calls += 1
                failure = case.get("page_failure")
                if failure is not None and calls == failure["call"]:
                    raise _PAGE_ERRORS[failure["raise"]](failure["message"])
                page = build_page(document, facts)
                mismatch = case.get("read_back_mismatch")
                if mismatch is not None and calls == mismatch["call"]:
                    page["claims"] = tuple(page["claims"])
                return page

            patches.enter_context(patch.object(
                _BUILD_PAGES, "build_page", side_effect=build_page_for_case,
            ))
        if case.get("index_read_back_mismatch"):
            def build_index_for_case(registry, pages):
                index = build_index(registry, pages)
                index["assets"] = tuple(index["assets"])
                return index

            patches.enter_context(patch.object(
                _BUILD_PAGES, "build_index", side_effect=build_index_for_case,
            ))
        if "write_pages_raises" in case:
            patches.enter_context(patch.object(
                _BUILD_PAGES, "write_pages",
                side_effect=RuntimeError(case["write_pages_raises"]),
            ))

    def _exercise_write(self, case, registry, context, documents, out_dir):
        def write():
            try:
                return _BUILD_PAGES.write_pages(registry, context, documents, out_dir)
            except Exception as error:
                if "message_equals" in case:
                    self.assertEqual(str(error), case["message_equals"])
                raise

        if "expected_error" in case:
            assert_exact_error(self, case, write, _ERRORS)
        else:
            summary = write()
            assert_result_equal(self, summary, case["expected_summary"], tolerance=0)

    def _exercise_cli(self, case, registry, context, documents, root):
        registry_path = root / "pipeline" / "instruments.json"
        registry_path.parent.mkdir()
        registry_path.write_text(
            case.get("registry_text", json.dumps(registry)), encoding="utf-8",
        )
        if not case.get("context_missing"):
            context_path = root / "words" / "context.json"
            context_path.parent.mkdir()
            context_path.write_text(json.dumps(context), encoding="utf-8")
        derived_dir = root / "data" / "derived"
        derived_dir.mkdir(parents=True)
        for instrument_id, document in documents.items():
            (derived_dir / (instrument_id + ".json")).write_text(
                json.dumps(document), encoding="utf-8",
            )

        out = StringIO()
        exit_code = _BUILD_PAGES.main(deepcopy(case["argv"]), root, out)
        assert_result_equal(self, exit_code, case["expected_exit"], tolerance=0)
        stdout = out.getvalue()
        self.assertEqual(stdout, "".join(line + "\n" for line in case["expected_stdout"]))
        for required_text in case.get("message_must_contain", []):
            self.assertIn(required_text, stdout)
        for forbidden_text in case.get("message_must_not_contain", []):
            self.assertNotIn(forbidden_text, stdout)

    def exercise_case(self, case):
        registry = apply_edits(_GOLDEN["registry"], case.get("registry_edits", []))
        context = apply_edits(_GOLDEN["context"], case.get("context_edits", []))
        documents = {
            instrument_id: apply_edits(
                _GOLDEN["documents"][fixture],
                case.get("document_edits", {}).get(instrument_id, []),
            )
            for instrument_id, fixture in case["documents"].items()
        }
        pages = _expected_pages(case, registry, context, documents)

        with tempfile.TemporaryDirectory() as temporary_root, ExitStack() as patches:
            root = Path(temporary_root)
            out_dir = root / "site" / "data"
            self._patch_builders(case, patches)
            if case["check"] == "write":
                if not case.get("out_dir_missing"):
                    self._prepare_output(out_dir, case.get("before_files", {}))
                self._exercise_write(case, registry, context, documents, out_dir)
            elif case["check"] == "cli":
                if "before_files" in case:
                    self._prepare_output(out_dir, case["before_files"])
                self._exercise_cli(case, registry, context, documents, root)
            else:
                self.fail("Unsupported golden check type: {}".format(case["check"]))
            self._assert_files(case, out_dir, pages)


generate_golden_tests(BuildPagesGoldenTests, _GOLDEN["cases"], {"write", "cli"})


if __name__ == "__main__":
    unittest.main()
