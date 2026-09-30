"""The provider connection boundary, replaced by an in-memory fake in tests."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pipeline.providers import ProviderError


def _identifier(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 64
        and all(character in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in value)
    )


def _http_error_detail(error):
    """Return a safe provider error identifier, or None for any bad body."""
    try:
        payload = json.loads(error.read())
        details = payload.get("error") if type(payload) is dict else None
        if type(details) is not dict:
            return None
        for field in ("code", "type"):
            if _identifier(details.get(field)):
                return details[field]
    except Exception:
        return None
    return None


def http_get_json(url, headers):
    """Fetch one JSON response without exposing connection or response contents."""
    try:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=30) as response:
            body = response.read()
    except HTTPError as error:
        raise ProviderError("HTTP {}".format(error.code)) from None
    except (socket.timeout, TimeoutError):
        raise ProviderError("timed out") from None
    except URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            raise ProviderError("timed out") from None
        raise ProviderError(
            "connection problem ({})".format(type(error.reason).__name__)
        ) from None
    except Exception as error:
        raise ProviderError(
            "connection problem ({})".format(type(error).__name__)
        ) from None

    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ProviderError("response was not JSON") from None


def http_post_json(url, headers, body):
    """POST one JSON request without exposing request or response contents."""
    encoded = json.dumps(body, allow_nan=False).encode("utf-8")
    try:
        request = Request(url, data=encoded, headers=headers, method="POST")
        with urlopen(request, timeout=120) as response:
            response_body = response.read()
    except HTTPError as error:
        message = "HTTP {}".format(error.code)
        detail = _http_error_detail(error)
        if detail is not None:
            message += " ({})".format(detail)
        raise ProviderError(message) from None
    except (socket.timeout, TimeoutError):
        raise ProviderError("timed out") from None
    except URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            raise ProviderError("timed out") from None
        raise ProviderError(
            "connection problem ({})".format(type(error.reason).__name__)
        ) from None
    except Exception as error:
        raise ProviderError(
            "connection problem ({})".format(type(error).__name__)
        ) from None

    try:
        return json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ProviderError("response was not JSON") from None
