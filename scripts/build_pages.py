"""Build and write page data offline in methodology section 14 order."""

import json
import os
from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from pipeline.publish import (
    PublishError, RegistryError, check_document, check_registry,
)
from words.cards import WordsError
from words.page import build_index, build_page, check_context


_MESSAGE_ERRORS = (RegistryError, PublishError, WordsError)


class PageError(Exception):
    """Identify the failed step without exposing arbitrary exception contents."""


def _page_error(who, step, error):
    message = "{}: {}: {}".format(who, step, type(error).__name__)
    if type(error) in _MESSAGE_ERRORS:
        message += ": " + str(error)
    return PageError(message)


def _step(who, step, action, *args):
    try:
        return action(*args)
    except Exception as error:
        raise _page_error(who, step, error) from None


def _asset_ids(registry):
    return [
        item["id"] for item in registry["instruments"] if item["role"] == "asset"
    ]


def _check_output_folder(out_dir, asset_ids):
    if not out_dir.is_dir():
        raise PageError("output folder: does not exist")
    allowed_names = {instrument_id + ".json" for instrument_id in asset_ids}
    allowed_names.add("index.json")
    names = _step("registry", "check", os.listdir, out_dir)
    for name in sorted(names):
        if name.startswith("."):
            continue
        path = out_dir / name
        if name not in allowed_names or not path.is_file() or path.is_symlink():
            raise PageError("output folder: unexpected " + name)


def _load_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _write_temporary(path, value, temporary_paths):
    text = json.dumps(
        value, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False,
    ) + "\n"
    # Exclusive creation prevents following a newly introduced link.
    with path.open("x", encoding="utf-8") as temporary_file:
        temporary_paths.append(path)
        temporary_file.write(text)


def _write_values(values, out_dir):
    temporary_paths = []
    try:
        for name, value in values:
            _step(
                name, "write", _write_temporary,
                out_dir / (name + ".tmp"), value, temporary_paths,
            )

        # Read every file back before replacing even the first existing file.
        for name, value in values:
            read_back = _step(name, "write", _load_json, out_dir / (name + ".tmp"))
            if read_back != value:
                raise PageError(name + ": write: read back differently")

        for name, value in values:
            _step(name, "write", os.replace, out_dir / (name + ".tmp"), out_dir / name)
    except Exception:
        # Keep attempting cleanup if one removal fails; never expose OS messages.
        for path in temporary_paths:
            try:
                path.unlink()
            except OSError:
                pass
        raise


def write_pages(registry, context, documents, out_dir):
    """Validate and build every page and the index before replacing any file."""
    _step("registry", "check", check_registry, registry)
    _step("context", "check", check_context, context, registry)
    asset_ids = _asset_ids(registry)
    out_dir = Path(out_dir)
    _check_output_folder(out_dir, asset_ids)

    for instrument_id in asset_ids:
        if instrument_id not in documents:
            raise PageError(instrument_id + ": document: missing")
    for instrument_id in sorted(documents):
        if instrument_id not in asset_ids:
            raise PageError("documents: unexpected " + instrument_id)

    pages = []
    for instrument_id in asset_ids:
        document = documents[instrument_id]
        _step(instrument_id, "check", check_document, document, registry)
        if document["instrument"]["id"] != instrument_id:
            raise PageError("{}: document: for {}".format(
                instrument_id, document["instrument"]["id"],
            ))
        facts = {
            key: value for key, value in context["instruments"][instrument_id].items()
            if key != "why"
        }
        pages.append(_step(instrument_id, "page", build_page, document, facts))

    index = _step("index", "build", build_index, registry, pages)
    values = [
        (instrument_id + ".json", page)
        for instrument_id, page in zip(asset_ids, pages)
    ] + [("index.json", index)]
    _write_values(values, out_dir)
    return {
        "data_as_of": index["data_as_of"],
        "generated_on": index["generated_on"],
        "method_version": index["method_version"],
        "written": [name for name, value in values],
    }


def main(argv, root, out):
    """Load committed inputs and return an exit code with a value-free report."""
    if argv:
        print("Usage: python3 scripts/build_pages.py", file=out)
        return 2

    root = Path(root)
    try:
        registry = _load_json(root / "pipeline" / "instruments.json")
    except Exception as error:
        print("FAILED: registry: load: " + type(error).__name__, file=out)
        print("Nothing was written.", file=out)
        return 1

    try:
        check_registry(registry)
    except Exception as error:
        message = "FAILED: registry: check: " + type(error).__name__
        if type(error) is RegistryError:
            message += ": " + str(error)
        print(message, file=out)
        print("Nothing was written.", file=out)
        return 1

    who = "context"
    try:
        context = _load_json(root / "words" / "context.json")
        documents = {}
        for who in _asset_ids(registry):
            documents[who] = _load_json(root / "data" / "derived" / (who + ".json"))
    except Exception as error:
        print("FAILED: {}: load: {}".format(who, type(error).__name__), file=out)
        print("Nothing was written.", file=out)
        return 1

    try:
        out_dir = root / "site" / "data"
        out_dir.mkdir(parents=True, exist_ok=True)
        summary = write_pages(registry, context, documents, out_dir)
        print("Data as of {data_as_of}, generated on {generated_on}, method {method_version}.".format(
            **summary
        ), file=out)
        print("Wrote {} files to site/data.".format(len(summary["written"])), file=out)
        return 0
    except PageError as error:
        print("FAILED: " + str(error), file=out)
    except Exception as error:
        print("FAILED: unexpected {}.".format(type(error).__name__), file=out)
    print("Check git status --short before committing anything.", file=out)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], _REPO_ROOT, sys.stdout))
