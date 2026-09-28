"""Golden provider tests with every connection and pause replaced in memory."""

import socket
import ssl
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from pipeline.network import http_get_json
from pipeline.providers import (
    ProviderError,
    build_requests,
    fetch_rows,
    parse_response,
)
from golden_support import (
    apply_edits,
    assert_exact_error,
    assert_result_equal,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("providers.json")
_ERRORS = {"ProviderError": ProviderError, "ValueError": ValueError}


class _FakeResponse:
    def __init__(self, body_text):
        self.body = body_text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def read(self):
        return self.body


class ProviderGoldenTests(unittest.TestCase):
    def _assert_case(self, case, calculate):
        if "expected_error" in case:
            assert_exact_error(self, case, calculate, _ERRORS)
        else:
            assert_result_equal(self, calculate(), case["expected"], tolerance=0)

    def _exercise_network(self, case):
        calls = []

        def fake_urlopen(*args, **kwargs):
            calls.append((args, kwargs))
            mode = case["network"]
            if mode == "http_error":
                raise HTTPError(case["url"], case["code"], "x", {}, None)
            if mode == "url_error":
                raise URLError(ssl.SSLError("x"))
            if mode == "socket_timeout":
                raise socket.timeout()
            if mode == "body":
                return _FakeResponse(case["body_text"])
            self.fail("Unsupported fake network mode: {}".format(mode))

        with patch("pipeline.network.urlopen", side_effect=fake_urlopen):
            self._assert_case(
                case, lambda: http_get_json(case["url"], case["headers"])
            )

        if "expected_request" in case:
            expected = case["expected_request"]
            self.assertEqual(len(calls), 1)
            args, kwargs = calls[0]
            self.assertEqual(len(args), 1)
            request = args[0]
            self.assertIsInstance(request, Request)
            assert_result_equal(self, request.get_method(), "GET", tolerance=0)
            assert_result_equal(self, request.full_url, expected["url"], tolerance=0)
            assert_result_equal(
                self,
                {name.lower(): value for name, value in request.header_items()},
                {name.lower(): value for name, value in expected["headers"].items()},
                tolerance=0,
            )
            assert_result_equal(self, kwargs, {"timeout": 30}, tolerance=0)

    def exercise_case(self, case):
        check = case["check"]
        if check == "http_get_json":
            self._exercise_network(case)
            return

        data = apply_edits(
            _GOLDEN["data"][case["data"]], case.get("data_edits", [])
        )
        if check == "build_requests":
            self._assert_case(
                case, lambda: build_requests(data, case["key"], case["as_of_month"])
            )
            return

        if check == "parse_response":
            self._assert_case(
                case, lambda: parse_response(data, case["payload"], case["key"])
            )
            return

        if check == "fetch_rows":
            calls = []
            waits = []

            def fake_http_get(url, headers):
                calls.append((url, dict(headers)))
                self.assertIn(url, case["responses"])
                response = case["responses"][url]
                if isinstance(response, dict) and "raise" in response:
                    raise ProviderError(response["raise"])
                return response

            def fake_wait(seconds):
                waits.append(seconds)

            self._assert_case(
                case,
                lambda: fetch_rows(
                    data, case["key"], case["as_of_month"],
                    fake_http_get, fake_wait,
                ),
            )
            if "expected_calls" in case:
                assert_result_equal(
                    self, [url for url, headers in calls],
                    case["expected_calls"], tolerance=0,
                )
            if "expected_waits" in case:
                assert_result_equal(
                    self, waits, case["expected_waits"], tolerance=0
                )
            return

        self.fail("Unsupported golden check type: {}".format(check))


generate_golden_tests(
    ProviderGoldenTests,
    _GOLDEN["cases"],
    {"build_requests", "parse_response", "fetch_rows", "http_get_json"},
)


if __name__ == "__main__":
    unittest.main()
