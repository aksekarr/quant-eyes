"""Plan an offline data build, or run it with explicitly supplied dependencies."""

import datetime
import json
import os
from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from pipeline.monthly import last_complete_month
from pipeline.providers import PAUSE_SECONDS, build_requests
from pipeline.publish import RegistryError, check_registry
from pipeline.runner import RunError, _series_entries, run


def _request_count(count):
    return "{} request{}".format(count, "" if count == 1 else "s")


def _print_plan(registry, today, out):
    as_of = last_complete_month(today)
    total = 0
    seconds = 0
    lines = ["Plan: data as of {} (run on {}).".format(as_of, today.isoformat())]
    for who, entry in _series_entries(registry):
        data = entry["data"]
        count = len(build_requests(data, "PLACEHOLDER", as_of))
        total += count
        seconds += count * PAUSE_SECONDS[data["provider"]]
        lines.append("{}: {} {} {}, {}".format(
            who, data["provider"], data["kind"], data["symbol"], _request_count(count),
        ))
    lines.append("{}, {} seconds of pauses. No requests made.".format(
        _request_count(total), seconds,
    ))
    for line in lines:
        print(line, file=out)


def main(argv, environ, today, out, root, make_fetch):
    """Return an exit code; the caller must explicitly supply the fetch factory."""
    if argv not in ([], ["--list"]):
        print("Usage: python3 scripts/build_data.py [--list]", file=out)
        return 2

    try:
        with (Path(root) / "pipeline" / "instruments.json").open(encoding="utf-8") as source:
            registry = json.load(source)
    except Exception as error:
        print("FAILED: registry: load: " + type(error).__name__, file=out)
        print("Nothing was fetched or written.", file=out)
        return 1

    try:
        check_registry(registry)
    except Exception as error:
        message = "FAILED: registry: check: " + type(error).__name__
        if type(error) is RegistryError:
            message += ": " + str(error)
        print(message, file=out)
        print("Nothing was fetched or written.", file=out)
        return 1

    try:
        if argv == ["--list"]:
            _print_plan(registry, today, out)
            return 0

        used_providers = {
            entry["data"]["provider"] for who, entry in _series_entries(registry)
        }
        keys = {}
        missing = False
        for provider in registry["providers"]:
            if provider not in used_providers:
                continue
            name = provider.upper() + "_API_KEY"
            key = environ.get(name)
            if not key:
                print("FAILED: {} is not set in this terminal.".format(name), file=out)
                missing = True
            else:
                keys[provider] = key
        if missing:
            print("Nothing was fetched or written.", file=out)
            return 1

        out_dir = Path(root) / "data" / "derived"
        out_dir.mkdir(parents=True, exist_ok=True)
        fetch = make_fetch(keys)
        summary = run(registry, fetch, today, out_dir)
        print("Data as of {} (run on {}).".format(
            summary["as_of"], today.isoformat(),
        ), file=out)
        for series in summary["series"]:
            print("{id}: {first} to {last} ({month_ends} month-ends)".format(
                **series
            ), file=out)
        print("Wrote {} files to data/derived. No prices were printed or saved.".format(
            len(summary["written"]),
        ), file=out)
        return 0
    except RunError as error:
        print("FAILED: " + str(error), file=out)
    except Exception as error:
        print("FAILED: unexpected {}.".format(type(error).__name__), file=out)
    print("Check git status --short before committing anything.", file=out)
    return 1


if __name__ == "__main__":
    import time

    from pipeline.network import http_get_json
    from pipeline.providers import fetch_rows

    def make_fetch(keys):
        def fetch(data, as_of_month):
            return fetch_rows(
                data, keys[data["provider"]], as_of_month, http_get_json, time.sleep,
            )
        return fetch

    sys.exit(main(
        sys.argv[1:], os.environ, datetime.date.today(), sys.stdout,
        _REPO_ROOT, make_fetch,
    ))
