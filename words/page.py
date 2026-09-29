"""Validate context and assemble page and landing data for section 13."""

from copy import deepcopy

from pipeline.publish import (
    RegistryError,
    _check_keys,
    _check_text,
    _check_url,
    _date_from_text,
)
from words.cards import (
    WordsError,
    _formatted,
    _identifier,
    _required,
    build_cards,
    month_name,
)
from words.cards_567 import build_cards_567


PAGE_VERSION = "1"
INDEX_VERSION = "1"


def _error_name(name, position):
    """Name a context key without allowing a URL into an error message."""
    if (
        isinstance(name, str) and name.strip()
        and all(character.isalnum() or character in " _-" for character in name)
    ):
        return name
    return "at position {}".format(position)


def _text(value, part):
    try:
        _check_text(value, part)
    except RegistryError as error:
        raise WordsError(str(error)) from None


def check_context(context, registry):
    """Check facts against an already checked instrument registry."""
    _check_keys(
        context, ("about", "facts_checked", "sources", "instruments"),
        "context", WordsError,
    )
    _text(context["about"], "context about")
    _date_from_text(context["facts_checked"], "context facts_checked", WordsError)

    sources = context["sources"]
    if type(sources) is not dict or not sources:
        raise WordsError("sources must be a non-empty dictionary.")
    for position, (name, url) in enumerate(sources.items(), 1):
        part = "sources " + _error_name(name, position)
        _text(name, part + " name")
        try:
            _check_url(url, part)
        except RegistryError as error:
            raise WordsError(str(error)) from None

    instruments = context["instruments"]
    if type(instruments) is not dict:
        raise WordsError("instruments must be a dictionary.")
    assets = {
        item["id"]: item for item in registry["instruments"]
        if item["role"] == "asset"
    }
    for instrument_id in assets:
        if instrument_id not in instruments:
            raise WordsError("instruments is missing {}.".format(instrument_id))
    for position, (instrument_id, facts) in enumerate(instruments.items(), 1):
        part = "instrument " + _error_name(instrument_id, position)
        if instrument_id not in assets:
            raise WordsError("{} is not an asset in the registry.".format(part))
        _check_keys(
            facts, ("held_by_tracker", "priced_in_pounds_holds_dollars", "why"),
            part, WordsError,
        )
        for field in ("held_by_tracker", "priced_in_pounds_holds_dollars"):
            if type(facts[field]) is not bool:
                raise WordsError("{} {} must be a boolean.".format(part, field))
        _text(facts["why"], part + " why")
        if (
            facts["priced_in_pounds_holds_dollars"]
            and assets[instrument_id]["identity"]["trading_currency"] != "GBP"
        ):
            raise WordsError(
                "{} priced_in_pounds_holds_dollars requires GBP trading_currency."
                .format(part)
            )


def build_page(document, facts):
    """Combine both card builders with the published document's metadata."""
    data_as_of = _required(document, "data_as_of")
    data_as_of_text = "Data to the end of {}".format(
        _formatted(document, "data_as_of", month_name)
    )
    generated_on = _required(document, "generated_on")
    sources = _required(document, "sources")
    method_version = _required(_required(document, "results"), "method_version")
    first = build_cards(document)
    last = build_cards_567(document, facts)
    claims = first["claims"] + last["claims"]
    claim_ids = set()
    for claim in claims:
        if claim["id"] in claim_ids:
            raise WordsError("Duplicate claim id: {}.".format(claim["id"]))
        claim_ids.add(claim["id"])
    return {
        "page_version": PAGE_VERSION,
        "instrument": deepcopy(document["instrument"]),
        "benchmark": deepcopy(document["benchmark"]),
        "data_as_of": data_as_of,
        "data_as_of_text": data_as_of_text,
        "generated_on": generated_on,
        "method_version": method_version,
        "sources": deepcopy(sources),
        "cards": first["cards"] + last["cards"],
        "claims": claims,
        "headline": None,
    }


def build_index(registry, pages):
    """Check page coverage and shared metadata, then use registry display order."""
    assets = {
        item["id"]: item for item in registry["instruments"]
        if item["role"] == "asset"
    }
    pages_by_id = {}
    for position, page in enumerate(pages, 1):
        instrument_id = _identifier(page, "instrument")
        part = "instrument " + _error_name(instrument_id, position)
        if instrument_id not in assets:
            raise WordsError("{} is not an asset in the registry.".format(part))
        if instrument_id in pages_by_id:
            raise WordsError("{} has duplicate pages.".format(part))
        pages_by_id[instrument_id] = page

    # Finish checking membership and duplicates before comparing any metadata.
    shared = {}
    for instrument_id, page in pages_by_id.items():
        for field in ("data_as_of", "generated_on", "method_version"):
            value = _required(page, field)
            if field in shared and value != shared[field]:
                raise WordsError("{} has inconsistent {}.".format(instrument_id, field))
            shared[field] = value

    for instrument_id in assets:
        if instrument_id not in pages_by_id:
            raise WordsError("{} is missing a page.".format(instrument_id))
    if not pages_by_id:
        raise WordsError("pages must contain at least one asset page.")

    first_page = next(iter(pages_by_id.values()))
    benchmark = next(
        item for item in registry["instruments"] if item["role"] == "benchmark"
    )

    def entry(instrument, identity_fields):
        result = {field: instrument[field] for field in ("id", "label")}
        result.update(
            (field, instrument["identity"][field]) for field in identity_fields
        )
        return result

    return {
        "index_version": INDEX_VERSION,
        "data_as_of": shared["data_as_of"],
        "data_as_of_text": _required(first_page, "data_as_of_text"),
        "generated_on": shared["generated_on"],
        "method_version": shared["method_version"],
        "benchmark": entry(benchmark, ("name", "ticker")),
        "assets": [
            entry(asset, ("name", "ticker", "type")) for asset in assets.values()
        ],
    }
