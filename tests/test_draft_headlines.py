"""Golden headline drafting tests with every request replaced in memory."""

import ast
from copy import deepcopy
import datetime
import importlib.util
import inspect
from io import BytesIO, StringIO
import json
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import words.headline as headline_module
from pipeline.network import http_post_json
from pipeline.providers import ProviderError
from words.cards import WordsError
from words.headline import check_headline, draft_request, read_draft
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("draft_headlines.json")
_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "draft_headlines.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "draft_headlines_under_test", _SCRIPT_PATH
)
_DRAFT_HEADLINES = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(_DRAFT_HEADLINES)
_ERRORS = {
    "ProviderError": ProviderError,
    "ValueError": ValueError,
    "WordsError": WordsError,
}
_FAKE_RAISES = {
    "ProviderError": ProviderError,
    "RuntimeError": RuntimeError,
}


class _FakeResponse:
    def __init__(self, body_text):
        self.body = body_text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def read(self):
        return self.body


class _UnreadableBody:
    def read(self):
        raise OSError("SECRETWORD")

    def close(self):
        pass


class DraftHeadlinesGoldenTests(unittest.TestCase):
    def _assert_case(self, case, calculate):
        if "expected_error" in case:
            def calculate_and_check_message():
                try:
                    return calculate()
                except Exception as error:
                    if "expected_message" in case:
                        self.assertEqual(str(error), case["expected_message"])
                    for text in case.get("message_must_not_contain", []):
                        self.assertNotIn(text, str(error))
                    raise

            assert_exact_error(
                self, case, calculate_and_check_message, _ERRORS
            )
        else:
            assert_result_equal(
                self, calculate(), case["expected"], tolerance=0
            )

    def _exercise_network(self, case):
        calls = []

        def fake_urlopen(*args, **kwargs):
            calls.append((args, kwargs))
            mode = case["network"]
            if mode == "body":
                return _FakeResponse(case["body_text"])
            if mode == "http_error":
                if case.get("error_body_raises"):
                    body = _UnreadableBody()
                elif case.get("error_body_text") is None:
                    body = None
                else:
                    body = BytesIO(case["error_body_text"].encode("utf-8"))
                raise HTTPError(case["url"], case["code"], "x", {}, body)
            if mode == "url_error":
                raise URLError(ssl.SSLError("x"))
            if mode == "url_error_timeout":
                raise URLError(socket.timeout())
            if mode == "socket_timeout":
                raise socket.timeout()
            if mode == "timeout_error":
                raise TimeoutError()
            if mode == "reset":
                raise ConnectionResetError()
            self.fail("Unsupported fake network mode: {}".format(mode))

        body = deepcopy(case["body"])
        if "body_nan_key" in case:
            body[case["body_nan_key"]] = float("nan")
        with patch("pipeline.network.urlopen", side_effect=fake_urlopen):
            self._assert_case(
                case,
                lambda: http_post_json(
                    case["url"], deepcopy(case["headers"]), body
                ),
            )

        if case.get("expected_no_call"):
            self.assertEqual(calls, [])
        if "expected_request" in case:
            expected = case["expected_request"]
            self.assertEqual(len(calls), 1)
            args, kwargs = calls[0]
            self.assertEqual(len(args), 1)
            request = args[0]
            self.assertIsInstance(request, Request)
            assert_result_equal(
                self, request.full_url, expected["url"], tolerance=0
            )
            assert_result_equal(
                self, request.get_method(), expected["method"], tolerance=0
            )
            assert_result_equal(
                self,
                {name.lower(): value for name, value in request.header_items()},
                {name.lower(): value for name, value in expected["headers"].items()},
                tolerance=0,
            )
            self.assertIs(type(request.data), bytes)
            assert_result_equal(
                self,
                json.loads(request.data.decode("utf-8")),
                expected["body"],
                tolerance=0,
            )
            assert_result_equal(
                self, kwargs, {"timeout": expected["timeout"]}, tolerance=0
            )

    def _prepare_cli_root(self, case, root):
        registry = apply_edits(
            _GOLDEN["registry"], case.get("registry_edits", [])
        )
        registry_path = root / "pipeline" / "instruments.json"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(
            case.get("registry_text", json.dumps(registry)), encoding="utf-8"
        )

        if not case.get("words_missing"):
            (root / "words").mkdir()
        pages = {}
        data_dir = root / "site" / "data"
        data_dir.mkdir(parents=True)
        for asset_id, fixture in case["pages"].items():
            page = apply_edits(
                _GOLDEN["pages"][fixture],
                case.get("page_edits", {}).get(asset_id, []),
            )
            pages[asset_id] = page
            if asset_id in case.get("page_text", {}):
                page_text = case["page_text"][asset_id]
            else:
                page_text = json.dumps(page)
            (data_dir / (asset_id + ".json")).write_text(
                page_text, encoding="utf-8"
            )
        for asset_id, page_text in case.get("page_text", {}).items():
            if asset_id not in case["pages"]:
                (data_dir / (asset_id + ".json")).write_text(
                    page_text, encoding="utf-8"
                )

        for relative_path, contents in case.get("before_files", {}).items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
        if case.get("drafts_is_folder"):
            (root / "words" / "headline_drafts.json").mkdir()
        return registry, pages

    def _assert_cli_calls(self, case, calls, pages):
        expected_calls = case["expected_calls"]
        self.assertEqual(len(calls), len(expected_calls))
        key = case["environ"].get("QX_OPENAI_API_KEY")
        for (url, headers, body), asset_id in zip(calls, expected_calls):
            assert_result_equal(
                self, url, "https://api.openai.com/v1/responses", tolerance=0
            )
            assert_result_equal(
                self,
                headers,
                {
                    "Authorization": "Bearer " + key,
                    "Content-Type": "application/json",
                },
                tolerance=0,
            )
            assert_result_equal(
                self,
                body,
                draft_request(deepcopy(pages[asset_id])),
                tolerance=0,
            )

    def _assert_cli_drafts(self, case, root, registry, pages):
        drafts_path = root / "words" / "headline_drafts.json"
        expected = case["expected_drafts"]
        if expected is None:
            before = case.get("before_files", {})
            if "words/headline_drafts.json" in before:
                self.assertTrue(drafts_path.is_file())
                self.assertEqual(
                    drafts_path.read_text(encoding="utf-8"),
                    before["words/headline_drafts.json"],
                )
            elif case.get("drafts_is_folder"):
                self.assertTrue(drafts_path.is_dir())
                self.assertEqual(list(drafts_path.iterdir()), [])
            else:
                self.assertFalse(drafts_path.exists())
        else:
            expected = deepcopy(expected)
            for asset_id, draft in expected["drafts"].items():
                draft["problems"] = check_headline(
                    draft["text"], draft["claims"], pages[asset_id], registry
                )
            expected_text = json.dumps(
                expected,
                indent=2,
                sort_keys=True,
                allow_nan=False,
                ensure_ascii=False,
            ) + "\n"
            self.assertTrue(drafts_path.is_file())
            self.assertEqual(
                drafts_path.read_text(encoding="utf-8"), expected_text
            )
        self.assertFalse(
            (root / "words" / "headline_drafts.json.tmp").exists()
        )

    def _exercise_cli(self, case):
        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            registry, pages = self._prepare_cli_root(case, root)
            responses = list(case["responses"])
            calls = []

            def fake_post(url, headers, body):
                calls.append((url, deepcopy(headers), deepcopy(body)))
                index = len(calls) - 1
                if index >= len(responses):
                    self.fail("Fake post called more times than expected.")
                response = responses[index]
                if type(response) is dict and "raise" in response:
                    raise _FAKE_RAISES[response["raise"]](response["message"])
                return deepcopy(_GOLDEN["responses"][response])

            out = StringIO()
            exit_code = _DRAFT_HEADLINES.main(
                deepcopy(case["argv"]),
                deepcopy(case["environ"]),
                datetime.date.fromisoformat(case["today"]),
                root,
                out,
                fake_post,
            )
            assert_result_equal(
                self, exit_code, case["expected_exit"], tolerance=0
            )
            stdout = out.getvalue()
            self.assertEqual(
                stdout,
                "".join(line + "\n" for line in case["expected_stdout"]),
            )
            key = case["environ"].get("QX_OPENAI_API_KEY")
            if key:
                self.assertNotIn(key, stdout)
            for text in case.get("message_must_not_contain", []):
                self.assertNotIn(text, stdout)
            self._assert_cli_calls(case, calls, pages)
            self._assert_cli_drafts(case, root, registry, pages)

    def exercise_case(self, case):
        check = case["check"]
        if check == "constants":
            actual = {
                name: getattr(headline_module, name)
                for name in case["expected"]
            }
            assert_result_equal(
                self, actual, case["expected"], tolerance=0
            )
            return
        if check == "draft_request":
            page = apply_edits(
                _GOLDEN["pages"][case["page"]], case.get("page_edits", [])
            )
            self._assert_case(case, lambda: draft_request(page))
            return
        if check == "read_draft":
            self._assert_case(
                case, lambda: read_draft(deepcopy(case["response"]))
            )
            return
        if check == "http_post_json":
            self._exercise_network(case)
            return
        if check == "cli":
            self._exercise_cli(case)
            return
        self.fail("Unsupported golden check type: {}".format(check))


class DraftHeadlinesStructuralTests(unittest.TestCase):
    def test_main_has_no_default_arguments(self):
        signature = inspect.signature(_DRAFT_HEADLINES.main)
        self.assertEqual(
            list(signature.parameters),
            ["argv", "environ", "today", "root", "out", "post"],
        )
        for parameter in signature.parameters.values():
            self.assertIs(parameter.default, inspect.Parameter.empty)

    def test_pipeline_network_import_is_entry_point_only(self):
        source = _SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(_SCRIPT_PATH))

        def is_network_import(node):
            if isinstance(node, ast.Import):
                return any(
                    alias.name == "pipeline.network" for alias in node.names
                )
            return (
                isinstance(node, ast.ImportFrom)
                and node.module == "pipeline.network"
            )

        def is_entry_guard(node):
            if not isinstance(node, ast.If):
                return False
            test = node.test
            return (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"
            )

        imports = [node for node in ast.walk(tree) if is_network_import(node)]
        guards = [node for node in tree.body if is_entry_guard(node)]
        self.assertTrue(imports)
        self.assertEqual(len(guards), 1)
        guarded_import_ids = {
            id(node)
            for statement in guards[0].body
            for node in ast.walk(statement)
            if is_network_import(node)
        }
        self.assertEqual({id(node) for node in imports}, guarded_import_ids)


generate_golden_tests(
    DraftHeadlinesGoldenTests,
    _GOLDEN["cases"],
    {"constants", "draft_request", "read_draft", "http_post_json", "cli"},
)


if __name__ == "__main__":
    unittest.main()
