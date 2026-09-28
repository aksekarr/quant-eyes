"""The provider connection boundary, replaced by an in-memory fake in tests."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pipeline.providers import ProviderError


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
