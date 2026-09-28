"""Build all derived documents before replacing any published file."""

import datetime
import json
import os

from engine.output import OutputError, analyse
from engine.series import CoverageError, SeriesError
from pipeline.monthly import ProviderDataError, build_monthly_series, last_complete_month
from pipeline.providers import ProviderError
from pipeline.publish import (
    PublishError, RegistryError, build_document, check_document, check_registry,
)


_MESSAGE_ERRORS = (
    RegistryError, ProviderError, ProviderDataError, CoverageError,
    SeriesError, PublishError, OutputError,
)


class RunError(Exception):
    """Identify the failed step without exposing arbitrary exception contents."""


def _run_error(who, step, error):
    message = "{}: {}: {}".format(who, step, type(error).__name__)
    if type(error) in _MESSAGE_ERRORS:
        message += ": " + str(error)
    return RunError(message)


def _step(who, step, action, *args):
    try:
        return action(*args)
    except Exception as error:
        raise _run_error(who, step, error) from None


def _series_entries(registry):
    """Share the fetch order with the command's offline plan."""
    instruments = registry["instruments"]
    return [("fx", registry["fx"])] + [
        (item["id"], item)
        for role in ("benchmark", "asset")
        for item in instruments if item["role"] == role
    ]


def _check_output_folder(out_dir, asset_ids):
    if not os.path.isdir(out_dir):
        raise RunError("output folder: does not exist")
    allowed_names = {instrument_id + ".json" for instrument_id in asset_ids}
    names = _step("registry", "check", os.listdir, out_dir)
    for name in sorted(names):
        if name.startswith("."):
            continue
        path = os.path.join(out_dir, name)
        if (
            name not in allowed_names
            or not os.path.isfile(path)
            or os.path.islink(path)
        ):
            raise RunError("output folder: unexpected " + name)


def _fetch_series(who, entry, fetch, as_of, summaries):
    data = entry["data"]
    rows = _step(who, "fetch", fetch, data, as_of)
    series = _step(
        who, "series", build_monthly_series,
        entry["label"], data["currency"], data["basis"], rows, as_of, data["start"],
    )
    summaries.append({
        "id": who, "first": series.first_month, "last": series.last_month,
        "month_ends": len(series.months),
    })
    return series


def _write_documents(documents, registry, out_dir):
    temporary_paths = []
    try:
        for who, document in documents:
            text = json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
            path = os.path.join(out_dir, who + ".json.tmp")
            # Exclusive creation also prevents following a newly introduced link.
            with open(path, "x", encoding="utf-8") as temporary_file:
                temporary_paths.append(path)
                temporary_file.write(text)

        # Check every file as read from disk before replacing even the first one.
        for who, document in documents:
            path = os.path.join(out_dir, who + ".json.tmp")
            with open(path, encoding="utf-8") as temporary_file:
                check_document(json.load(temporary_file), registry)

        for who, document in documents:
            os.replace(
                os.path.join(out_dir, who + ".json.tmp"),
                os.path.join(out_dir, who + ".json"),
            )
    except Exception as error:
        # Keep attempting cleanup if one removal fails; never expose OS messages.
        for path in temporary_paths:
            try:
                os.remove(path)
            except OSError:
                pass
        raise _run_error(who, "write", error) from None


def run(registry, fetch, today, out_dir):
    """Fetch, calculate, check and publish in methodology section 10.2 order."""
    if not isinstance(today, datetime.date) or isinstance(today, datetime.datetime):
        raise ValueError("Today must be a date without a time.")
    _step("registry", "check", check_registry, registry)
    as_of = last_complete_month(today)
    entries = _series_entries(registry)
    _check_output_folder(out_dir, [who for who, entry in entries[2:]])

    summaries = []
    fx = _fetch_series(*entries[0], fetch, as_of, summaries)
    tracker = _fetch_series(*entries[1], fetch, as_of, summaries)
    documents = []
    for who, entry in entries[2:]:
        asset = _fetch_series(who, entry, fetch, as_of, summaries)
        results = _step(
            who, "analyse", analyse, asset, tracker,
            fx if entry["data"]["currency"] == "USD" else None,
        )
        document = _step(
            who, "document", build_document, registry, who, results, as_of, today,
        )
        documents.append((who, document))

    _write_documents(documents, registry, out_dir)
    return {
        "as_of": as_of,
        "series": summaries,
        "written": [who + ".json" for who, document in documents],
    }
