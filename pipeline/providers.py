"""Build provider requests and read in-memory responses without performing I/O."""

import re

from engine.series import _month_parts


PAUSE_SECONDS = {"tiingo": 1, "alphavantage": 13}
_PROVIDER_KINDS = (
    ("tiingo", "equity"),
    ("tiingo", "crypto"),
    ("alphavantage", "equity"),
    ("alphavantage", "fx"),
)


class ProviderError(Exception):
    """Raised when a provider cannot supply a readable response."""


def _check_data(data, key):
    """Check request identifiers without including their contents in errors."""
    if not isinstance(key, str) or re.fullmatch(r"[A-Za-z0-9]+", key) is None:
        raise ValueError("Key must contain letters and digits only and be non-empty.")
    if not isinstance(data, dict):
        raise ValueError("Data must be an instrument definition.")
    provider, kind = data.get("provider"), data.get("kind")
    if (provider, kind) not in _PROVIDER_KINDS:
        raise ValueError("Unsupported provider and kind.")
    symbol = data.get("symbol")
    pattern = r"[A-Z]{3}/[A-Z]{3}" if kind == "fx" else r"[A-Za-z0-9.]+"
    if not isinstance(symbol, str) or re.fullmatch(pattern, symbol) is None:
        raise ValueError("Symbol has an invalid format for its kind.")
    if not isinstance(data.get("field"), str) or not data["field"]:
        raise ValueError("Field must be non-empty text.")
    return provider, kind, symbol


def build_requests(data, key, as_of_month):
    """Validate all arguments, then return every request in execution order."""
    provider, kind, symbol = _check_data(data, key)
    as_of_parts = _month_parts(as_of_month)
    start = data.get("start")
    start_parts = _month_parts(start) if start is not None else None
    if kind == "crypto":
        if start_parts is None:
            raise ValueError("Crypto requires a start month.")
        if start_parts > as_of_parts:
            raise ValueError("Crypto start month must not follow the as-of month.")

    if provider == "tiingo":
        headers = {"Authorization": "Token " + key, "Content-Type": "application/json"}
        if kind == "equity":
            urls = [
                "https://api.tiingo.com/tiingo/daily/{}/prices?startDate=1990-01-01".format(
                    symbol
                )
            ]
        else:
            urls = [
                (
                    "https://api.tiingo.com/tiingo/crypto/prices?tickers={}"
                    "&startDate={:04d}-01-01&endDate={:04d}-12-31&resampleFreq=1day"
                ).format(symbol, year, year)
                for year in range(start_parts[0], as_of_parts[0] + 1)
            ]
    else:
        headers = {}
        base = "https://www.alphavantage.co/query?function="
        if kind == "equity":
            urls = [
                base + "TIME_SERIES_MONTHLY_ADJUSTED&symbol=" + symbol + "&apikey=" + key
            ]
        else:
            from_symbol, to_symbol = symbol.split("/")
            urls = [
                base + "FX_MONTHLY&from_symbol=" + from_symbol
                + "&to_symbol=" + to_symbol + "&apikey=" + key
            ]
    return [{"url": url, "headers": dict(headers)} for url in urls]


def _clean_message(message, key):
    """Clean known message text without stringifying arbitrary response data."""
    if not isinstance(message, str):
        return "Provider returned an invalid message."
    message = message.replace(key, "[key]")
    message = re.sub(r"apikey=[^&\s]*", "apikey=[key]", message)
    message = " ".join(message.split())

    def remove_url(match):
        # Keep evidence of key redaction without returning the provider's URL.
        return "[url] apikey=[key]" if "apikey=" in match.group() else "[url]"

    message = re.sub(
        r"\b(?:[a-z][a-z0-9+.-]*://|www\.)\S+", remove_url, message,
        flags=re.IGNORECASE,
    )
    return message[:200]


def _tiingo_rows(entries, field):
    if not isinstance(entries, list):
        raise ProviderError("Expected a list of rows.")
    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ProviderError("Expected an object for each row.")
        rows.append([entry.get("date"), entry.get(field)])
    return rows


def parse_response(data, payload, key):
    """Read only dates and the named field, preserving the provider's row order."""
    provider, kind, symbol = _check_data(data, key)
    field = data["field"]
    if provider == "tiingo":
        if isinstance(payload, dict):
            raise ProviderError(_clean_message(payload.get("detail"), key))
        if not isinstance(payload, list):
            raise ProviderError("Expected a list in the provider response.")
        if kind == "equity":
            return _tiingo_rows(payload, field)
        if not payload:
            return []
        if len(payload) != 1 or not isinstance(payload[0], dict):
            raise ProviderError("Expected at most one crypto object.")
        entry = payload[0]
        if "ticker" in entry and entry["ticker"] != symbol:
            raise ProviderError("Response ticker does not match the requested symbol.")
        return _tiingo_rows(entry.get("priceData"), field)

    if not isinstance(payload, dict):
        raise ProviderError("Expected an object in the provider response.")
    for message_field in ("Information", "Note", "Error Message"):
        if message_field in payload:
            raise ProviderError(_clean_message(payload[message_field], key))
    candidates = [name for name in payload if name != "Meta Data"]
    if len(candidates) != 1:
        raise ProviderError("Expected exactly one series in the provider response.")
    entries = payload[candidates[0]]
    if not isinstance(entries, dict):
        raise ProviderError("Expected an object of dates and entries.")
    return [
        [date, entry.get(field) if isinstance(entry, dict) else None]
        for date, entry in entries.items()
    ]


def fetch_rows(data, key, as_of_month, http_get, wait):
    """Build all requests, then pause, request and parse each until completion."""
    requests = build_requests(data, key, as_of_month)
    provider, symbol = data["provider"], data["symbol"]
    rows = []
    for request in requests:
        wait(PAUSE_SECONDS[provider])
        try:
            payload = http_get(request["url"], request["headers"])
            rows.extend(parse_response(data, payload, key))
        except ProviderError as error:
            raise ProviderError(
                "{} {}: {}".format(provider, symbol, _clean_message(str(error), key))
            ) from None
    return rows
