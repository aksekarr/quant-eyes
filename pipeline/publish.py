"""Validate instrument facts and assemble checked, derived-only documents."""

from copy import deepcopy
import datetime
import re

from engine.output import METHOD_VERSION, OutputError, check_output
from engine.series import _month_parts


DOCUMENT_VERSION = "1"

_ID_PATTERN = re.compile(r"[a-z][a-z0-9]{1,19}")
_FIELD_PATTERN = re.compile(r"[a-z][a-z0-9_]*")
_ISIN_PATTERN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")
_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_REGISTRY_KEYS = ("about", "facts_checked", "providers", "fx", "instruments")
_INSTRUMENT_KEYS = ("id", "role", "label", "identity", "data")
_IDENTITY_KEYS = (
    "name", "ticker", "type", "isin", "exchange", "share_class",
    "trading_currency", "quote_unit", "income", "currency_hedged", "sources",
)
_DATA_KEYS = ("provider", "kind", "symbol", "field", "currency", "basis", "start")
_DOCUMENT_KEYS = (
    "document_version", "instrument", "benchmark", "data_as_of",
    "generated_on", "sources", "results",
)
_RESULT_KEYS = ("method_version", "asset_currency", "own", "side_by_side", "currency")


class RegistryError(Exception):
    """Raised when the instrument list breaks a section 8.1 rule."""


class PublishError(Exception):
    """Raised when a document breaks a section 8.3 rule."""


def _check_keys(value, keys, part, error):
    if type(value) is not dict:
        raise error("{} must be a dictionary.".format(part))
    for key in keys:
        if key not in value:
            raise error("{} is missing field {}.".format(part, key))
    for key in value:
        if key not in keys:
            # Unknown field names are useful; arbitrary keys may contain URLs.
            field = (
                key if isinstance(key, str) and _FIELD_PATTERN.fullmatch(key)
                else "(invalid field name)"
            )
            raise error("{} has unexpected field {}.".format(part, field))


def _valid_id(value):
    return isinstance(value, str) and _ID_PATTERN.fullmatch(value) is not None


def _check_text(value, part):
    if not isinstance(value, str) or not value.strip():
        raise RegistryError("{} must be non-empty text.".format(part))


def _check_url(value, part):
    if (
        not isinstance(value, str)
        or not value.startswith("https://")
        or len(value) <= len("https://")
        or any(character in value for character in ("?", "#", " "))
    ):
        raise RegistryError("{} must be an https URL without a query, fragment or spaces.".format(part))


def _date_from_text(value, part, error):
    if not isinstance(value, str) or _DATE_PATTERN.fullmatch(value) is None:
        raise error("{} must use YYYY-MM-DD.".format(part))
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise error("{} must be a valid calendar date.".format(part)) from None


def _check_month(value, part, error):
    try:
        return _month_parts(value)
    except ValueError:
        raise error("{} must be a valid YYYY-MM month.".format(part)) from None


def _check_data(data, providers, part, kind, currency, basis):
    _check_keys(data, _DATA_KEYS, part, RegistryError)
    if not isinstance(data["provider"], str) or data["provider"] not in providers:
        raise RegistryError("{} provider must be listed in providers.".format(part))
    for field, expected in (("kind", kind), ("currency", currency), ("basis", basis)):
        if data[field] != expected:
            raise RegistryError("{} {} is inconsistent with its instrument or fx role.".format(part, field))
    for field in ("symbol", "field"):
        _check_text(data[field], part + " " + field)
    if data["start"] is not None:
        _check_month(data["start"], part + " start", RegistryError)


def _check_identity(identity, part):
    _check_keys(identity, _IDENTITY_KEYS, part, RegistryError)
    for field in ("name", "ticker"):
        _check_text(identity[field], part + " " + field)
    kind = identity["type"]
    if kind not in ("etf", "etc", "share", "cryptocurrency"):
        raise RegistryError("{} type is invalid.".format(part))

    isin = identity["isin"]
    if kind == "cryptocurrency":
        if isin is not None:
            raise RegistryError("{} isin must be null.".format(part))
        if identity["exchange"] is not None:
            raise RegistryError("{} exchange must be null.".format(part))
    else:
        if not isinstance(isin, str) or _ISIN_PATTERN.fullmatch(isin) is None:
            raise RegistryError("{} isin has an invalid format.".format(part))
        _check_text(identity["exchange"], part + " exchange")

    share_class = identity["share_class"]
    if kind == "cryptocurrency":
        if share_class is not None:
            raise RegistryError("{} share_class must be null.".format(part))
    elif kind == "etf" or share_class is not None:
        _check_text(share_class, part + " share_class")

    currency = identity["trading_currency"]
    if currency not in ("GBP", "USD"):
        raise RegistryError("{} trading_currency is invalid.".format(part))
    quote_units = ("pence", "pounds") if currency == "GBP" else ("dollars",)
    if identity["quote_unit"] not in quote_units:
        raise RegistryError("{} quote_unit does not match trading_currency.".format(part))

    incomes = {
        "etf": ("accumulating", "distributing"),
        "etc": ("none",),
        "share": ("dividends", "none"),
        "cryptocurrency": ("none",),
    }
    if identity["income"] not in incomes[kind]:
        raise RegistryError("{} income does not match type.".format(part))
    if kind in ("etf", "etc"):
        if type(identity["currency_hedged"]) is not bool:
            raise RegistryError("{} currency_hedged must be a boolean.".format(part))
    elif identity["currency_hedged"] is not None:
        raise RegistryError("{} currency_hedged must be null.".format(part))

    sources = identity["sources"]
    if type(sources) is not list or not sources:
        raise RegistryError("{} sources must be a non-empty list.".format(part))
    for source in sources:
        _check_url(source, part + " sources")


def check_registry(registry):
    """Check all instrument facts, raising RegistryError without echoing values."""
    _check_keys(registry, _REGISTRY_KEYS, "registry", RegistryError)
    _check_text(registry["about"], "registry about")
    _date_from_text(registry["facts_checked"], "registry facts_checked", RegistryError)

    providers = registry["providers"]
    if type(providers) is not dict or not providers:
        raise RegistryError("providers must be a non-empty dictionary.")
    for position, (provider_id, provider) in enumerate(providers.items(), 1):
        if not _valid_id(provider_id):
            raise RegistryError("Provider at position {} has an invalid id.".format(position))
        part = "provider " + provider_id
        _check_keys(provider, ("name", "url"), part, RegistryError)
        _check_text(provider["name"], part + " name")
        _check_url(provider["url"], part + " url")

    fx = registry["fx"]
    _check_keys(fx, ("label", "data"), "fx", RegistryError)
    _check_text(fx["label"], "fx label")
    _check_data(fx["data"], providers, "fx data", "fx", "USD", "fx_rate")

    instruments = registry["instruments"]
    if type(instruments) is not list or not instruments:
        raise RegistryError("instruments must be a non-empty list.")
    seen_ids = set()
    benchmarks = []
    for position, instrument in enumerate(instruments, 1):
        instrument_id = instrument.get("id") if type(instrument) is dict else None
        part = (
            "instrument " + instrument_id if _valid_id(instrument_id)
            else "instrument at position {}".format(position)
        )
        _check_keys(instrument, _INSTRUMENT_KEYS, part, RegistryError)
        if not _valid_id(instrument_id):
            raise RegistryError("{} id is invalid.".format(part))
        if instrument_id in seen_ids:
            raise RegistryError("{} id is duplicated.".format(part))
        seen_ids.add(instrument_id)
        if instrument["role"] not in ("benchmark", "asset"):
            raise RegistryError("{} role is invalid.".format(part))
        _check_text(instrument["label"], part + " label")
        identity = instrument["identity"]
        _check_identity(identity, part + " identity")
        _check_data(
            instrument["data"], providers, part + " data",
            "crypto" if identity["type"] == "cryptocurrency" else "equity",
            identity["trading_currency"], "total_return",
        )
        if instrument["role"] == "benchmark":
            if identity["trading_currency"] != "GBP":
                raise RegistryError("{} benchmark trading_currency must be GBP.".format(part))
            benchmarks.append(instrument_id)
            if len(benchmarks) > 1:
                raise RegistryError("{} role duplicates the benchmark.".format(part))
    if not benchmarks:
        raise RegistryError("instruments must contain exactly one benchmark.")


def _find_asset(registry, instrument_id):
    return next(
        (item for item in registry["instruments"]
         if item["id"] == instrument_id and item["role"] == "asset"),
        None,
    )


def _benchmark(registry):
    return next(item for item in registry["instruments"] if item["role"] == "benchmark")


def _identity_copy(instrument):
    return deepcopy({key: instrument[key] for key in ("id", "label", "identity")})


def _build_sources(registry, instrument, benchmark):
    """Group attribution by provider id in order of first use."""
    inputs = [instrument, benchmark]
    if instrument["data"]["currency"] == "USD":
        inputs.append(registry["fx"])
    sources = {}
    for item in inputs:
        provider_id = item["data"]["provider"]
        if provider_id not in sources:
            provider = registry["providers"][provider_id]
            sources[provider_id] = {
                "provider": provider["name"], "url": provider["url"], "used_for": [],
            }
        sources[provider_id]["used_for"].append(item["label"])
    return deepcopy(list(sources.values()))


def _same_copy(actual, expected):
    """Require matching types as well as values, including booleans in identity."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(
            _same_copy(actual[key], value) for key, value in expected.items()
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            _same_copy(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def build_document(registry, instrument_id, results, as_of_month, generated_on):
    """Build independent copies and check the finished document before returning."""
    check_registry(registry)
    instrument = _find_asset(registry, instrument_id)
    if instrument is None:
        raise ValueError("instrument_id must identify an asset in the registry.")
    as_of_parts = _check_month(as_of_month, "as_of_month", ValueError)
    if not isinstance(generated_on, datetime.date) or isinstance(generated_on, datetime.datetime):
        raise ValueError("generated_on must be a date without a time.")
    if (generated_on.year, generated_on.month) <= as_of_parts:
        raise ValueError("generated_on must be in a month after as_of_month.")

    benchmark = _benchmark(registry)
    document = {
        "document_version": DOCUMENT_VERSION,
        "instrument": _identity_copy(instrument),
        "benchmark": _identity_copy(benchmark),
        "data_as_of": as_of_month,
        "generated_on": generated_on.isoformat(),
        "sources": _build_sources(registry, instrument, benchmark),
        "results": deepcopy(results),
    }
    check_document(document, registry)
    return document


def check_document(document, registry):
    """Check section 8.3 in order against an already-checked registry."""
    _check_keys(document, _DOCUMENT_KEYS, "document", PublishError)
    if document["document_version"] != DOCUMENT_VERSION:
        raise PublishError("document_version is not current.")

    published_instrument = document["instrument"]
    if type(published_instrument) is not dict:
        raise PublishError("instrument must be an asset copied from the registry.")
    instrument = _find_asset(registry, published_instrument.get("id"))
    if instrument is None or not _same_copy(published_instrument, _identity_copy(instrument)):
        raise PublishError("instrument must be an asset copied exactly from the registry.")
    benchmark = _benchmark(registry)
    if not _same_copy(document["benchmark"], _identity_copy(benchmark)):
        raise PublishError("benchmark must be copied exactly from the registry.")

    as_of = document["data_as_of"]
    as_of_parts = _check_month(as_of, "data_as_of", PublishError)
    generated_on = _date_from_text(document["generated_on"], "generated_on", PublishError)
    if (generated_on.year, generated_on.month) <= as_of_parts:
        raise PublishError("generated_on must be in a month after data_as_of.")
    if not _same_copy(document["sources"], _build_sources(registry, instrument, benchmark)):
        raise PublishError("sources must match the registry attribution in order of use.")

    results = document["results"]
    # The engine owns permitted output shapes; OutputError passes through unchanged.
    check_output(results)
    _check_keys(results, _RESULT_KEYS, "results", PublishError)
    if results["method_version"] != METHOD_VERSION:
        raise PublishError("results method_version is not current.")
    currency = instrument["data"]["currency"]
    if results["asset_currency"] != currency:
        raise PublishError("results asset_currency does not match the instrument.")
    own = results["own"]
    if type(own) is not dict or own.get("end") != as_of:
        raise PublishError("results own must be present and end at data_as_of.")
    start = instrument["data"]["start"]
    if start is not None and own.get("start") != start:
        raise PublishError("results own start does not match the instrument start.")
    side = results["side_by_side"]
    if type(side) is not dict:
        raise PublishError("results side_by_side must be present.")
    for part in ("asset", "tracker"):
        profile = side.get(part)
        if type(profile) is not dict or profile.get("end") != as_of:
            raise PublishError("results side_by_side {} must end at data_as_of.".format(part))
    if currency == "USD":
        if type(results["currency"]) is not dict:
            raise PublishError("results currency must be present for a dollar instrument.")
    elif results["currency"] is not None:
        raise PublishError("results currency must be empty for a pound instrument.")
