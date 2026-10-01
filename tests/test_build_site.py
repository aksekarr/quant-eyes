"""Golden site writer and command tests using only temporary folders."""

from contextlib import ExitStack
from copy import deepcopy
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from web.render import SiteError, render_landing, render_page
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("build_site.json")
_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_site.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("build_site_under_test", _SCRIPT_PATH)
_BUILD_SITE = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(_BUILD_SITE)
_ERRORS = {"SiteWriteError": _BUILD_SITE.SiteWriteError}
_RENDER_ERRORS = {"SiteError": SiteError, "RuntimeError": RuntimeError}


class _UnequalText(str):
    """Encode normally, but never equal the text decoded from a written file."""

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    __hash__ = str.__hash__


def _expected_rendered(case, index, pages, reviews):
    """Use the already-tested renderer for the exact expected UTF-8 contents."""
    if not case["expected_rendered"]:
        return {}
    ordered_pages = [pages[asset["id"]] for asset in index["assets"]]
    texts = {
        "index.html": render_landing(
            deepcopy(index), deepcopy(ordered_pages), deepcopy(reviews),
        ),
    }
    for asset in index["assets"]:
        instrument_id = asset["id"]
        texts[instrument_id + "/index.html"] = render_page(
            deepcopy(pages[instrument_id]), deepcopy(index),
        )
    return {
        name: texts[name].encode("utf-8") for name in case["expected_rendered"]
    }


def _snapshot(out_dir):
    """Read every relative path, including folders, and every file's bytes."""
    tree = []
    files = {}
    for current, folders, names in os.walk(out_dir):
        directory = Path(current)
        for name in folders:
            tree.append((directory / name).relative_to(out_dir).as_posix() + "/")
        for name in names:
            path = directory / name
            relative = path.relative_to(out_dir).as_posix()
            tree.append(relative)
            files[relative] = path.read_bytes()
    return sorted(tree), files


class BuildSiteGoldenTests(unittest.TestCase):
    def _prepare_output(self, out_dir, before_files):
        out_dir.mkdir(parents=True)
        files = {}
        for name, contents in before_files.items():
            path = out_dir / name
            if isinstance(contents, dict) and contents.get("folder") is True:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                files[name] = contents.encode("utf-8")
                path.write_bytes(files[name])
        return files

    def _prepare_cli(self, case, index, pages, reviews, out_dir, original_files):
        data_dir = out_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        texts = {}
        if not case.get("index_missing"):
            texts["index.json"] = case.get("index_text", json.dumps(index))
        for instrument_id, page in pages.items():
            texts[instrument_id + ".json"] = case.get("page_texts", {}).get(
                instrument_id, json.dumps(page),
            )
        for name, contents in texts.items():
            encoded = contents.encode("utf-8")
            (data_dir / name).write_bytes(encoded)
            original_files["data/" + name] = encoded
        if not case.get("reviews_missing"):
            words_dir = out_dir.parent / "words"
            words_dir.mkdir()
            text = case.get("reviews_text", json.dumps(reviews))
            (words_dir / "review_record.json").write_bytes(text.encode("utf-8"))

    def _patch_renderers(self, case, patches):
        mismatch = case.get("read_back_mismatch")
        if "render_failure" in case or (mismatch and mismatch != "index.html"):
            calls = 0

            def render_page_for_case(page, index):
                nonlocal calls
                calls += 1
                failure = case.get("render_failure")
                if failure is not None and calls == failure["call"]:
                    raise _RENDER_ERRORS[failure["raise"]](failure["message"])
                text = render_page(page, index)
                if mismatch == page["instrument"]["id"] + "/index.html":
                    return _UnequalText(text)
                return text

            patches.enter_context(patch.object(
                _BUILD_SITE, "render_page", side_effect=render_page_for_case,
            ))
        if mismatch == "index.html":
            def render_landing_for_case(index, pages, reviews=None):
                return _UnequalText(render_landing(index, pages, reviews))

            patches.enter_context(patch.object(
                _BUILD_SITE, "render_landing", side_effect=render_landing_for_case,
            ))
        if "write_site_raises" in case:
            patches.enter_context(patch.object(
                _BUILD_SITE, "write_site",
                side_effect=RuntimeError(case["write_site_raises"]),
            ))

    def _exercise_write(self, case, index, pages, reviews, out_dir):
        def write():
            try:
                if "reviews" in case:
                    return _BUILD_SITE.write_site(index, pages, out_dir, reviews)
                return _BUILD_SITE.write_site(index, pages, out_dir)
            except _BUILD_SITE.SiteWriteError as error:
                if "expected_error" in case:
                    self.assertEqual(str(error), case["expected_error"])
                raise

        if "expected_error" in case:
            assert_exact_error(
                self, {"expected_error": "SiteWriteError"}, write, _ERRORS,
            )
            return None
        summary = write()
        assert_result_equal(self, summary, case["expected_summary"], tolerance=0)
        return summary

    def _exercise_cli(self, case, root):
        out = StringIO()
        exit_code = _BUILD_SITE.main(deepcopy(case["argv"]), root, out)
        assert_result_equal(self, exit_code, case["expected_exit"], tolerance=0)
        stdout = out.getvalue()
        self.assertEqual(stdout, "".join(line + "\n" for line in case["expected_stdout"]))
        return exit_code, stdout

    def _assert_output(self, case, out_dir, original_files, rendered):
        if case["expected_tree"] is None:
            self.assertFalse(out_dir.exists())
            return None
        self.assertTrue(out_dir.is_dir())
        tree, files = _snapshot(out_dir)
        assert_result_equal(self, tree, case["expected_tree"], tolerance=0)
        self.assertEqual(set(rendered), set(case["expected_rendered"]))
        expected_files = dict(original_files)
        expected_files.update(rendered)
        self.assertEqual(set(files), set(expected_files))
        for name, contents in expected_files.items():
            with self.subTest(path=name):
                self.assertEqual(files[name], contents)
        return tree, files

    def exercise_case(self, case):
        index = apply_edits(
            _GOLDEN["index"][case.get("index", "IDX3")], case.get("index_edits", []),
        )
        pages = {
            instrument_id: apply_edits(
                _GOLDEN["pages"][fixture],
                case.get("page_edits", {}).get(instrument_id, []),
            )
            for instrument_id, fixture in case["pages"].items()
        }
        reviews = None
        if "reviews" in case or case["check"] == "cli":
            reviews = apply_edits(
                _GOLDEN["reviews"][case.get("reviews", "REC3")],
                case.get("review_edits", []),
            )
        rendered = _expected_rendered(case, index, pages, reviews)

        with tempfile.TemporaryDirectory() as temporary_root, ExitStack() as patches:
            root = Path(temporary_root)
            out_dir = root / "site"
            original_files = {}
            if not case.get("out_dir_missing"):
                original_files = self._prepare_output(
                    out_dir, case.get("before_files", {}),
                )
            if case["check"] == "cli":
                self._prepare_cli(case, index, pages, reviews, out_dir, original_files)
                exercise = lambda: self._exercise_cli(case, root)
                successful = case["expected_exit"] == 0
            elif case["check"] == "write":
                exercise = lambda: self._exercise_write(
                    case, index, pages, reviews, out_dir,
                )
                successful = "expected_error" not in case
            else:
                self.fail("Unsupported golden check type: {}".format(case["check"]))
            self._patch_renderers(case, patches)
            first_result = exercise()
            first_snapshot = self._assert_output(case, out_dir, original_files, rendered)
            if successful:
                second_result = exercise()
                self.assertEqual(second_result, first_result)
                second_snapshot = self._assert_output(
                    case, out_dir, original_files, rendered,
                )
                self.assertEqual(second_snapshot, first_snapshot)


generate_golden_tests(BuildSiteGoldenTests, _GOLDEN["cases"], {"write", "cli"})


if __name__ == "__main__":
    unittest.main()
