"""Render and write the site's HTML offline in methodology section 17 order."""

import json
import os
from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from web.render import SiteError, render_landing, render_page


class SiteWriteError(Exception):
    """Identify the failed step without exposing arbitrary exception contents."""


def _asset_ids(index):
    if not isinstance(index, dict) or not isinstance(index.get("assets"), list):
        raise SiteWriteError("index: assets: unreadable")
    asset_ids = []
    for asset in index["assets"]:
        if not isinstance(asset, dict) or not isinstance(asset.get("id"), str):
            raise SiteWriteError("index: assets: unreadable")
        asset_ids.append(asset["id"])
    return asset_ids


def _check_output_folder(out_dir, asset_ids):
    if not out_dir.is_dir():
        raise SiteWriteError("output folder: does not exist")
    folder_names = set(asset_ids) | {"data", "assets"}
    for name in sorted(os.listdir(out_dir)):
        if name.startswith("."):
            continue
        path = out_dir / name
        if name in folder_names:
            allowed = path.is_dir()
        else:
            allowed = name == "index.html" and path.is_file()
        if not allowed or path.is_symlink():
            raise SiteWriteError("output folder: unexpected " + name)

    # Finish checking the top level before examining any asset folder.
    for instrument_id in asset_ids:
        folder = out_dir / instrument_id
        if not folder.exists():
            continue
        for name in sorted(os.listdir(folder)):
            if name.startswith("."):
                continue
            path = folder / name
            if name != "index.html" or not path.is_file() or path.is_symlink():
                raise SiteWriteError("output folder: unexpected {}/{}".format(
                    instrument_id, name,
                ))


def _write_step(name, action, *args):
    try:
        return action(*args)
    except Exception as error:
        raise SiteWriteError("{}: write: {}".format(
            name, type(error).__name__,
        )) from None


def _write_temporary(path, text, temporary_paths):
    # Binary mode preserves the rendered newlines; exclusive creation avoids
    # overwriting a file or following a link introduced since the folder check.
    with path.open("xb") as temporary_file:
        temporary_paths.append(path)
        temporary_file.write(text.encode("utf-8"))


def _read_text(path):
    return path.read_bytes().decode("utf-8")


def _write_values(values, asset_ids, out_dir):
    temporary_paths = []
    created_folders = []
    try:
        for instrument_id in asset_ids:
            folder = out_dir / instrument_id
            if not folder.exists():
                _write_step(instrument_id + "/index.html", folder.mkdir)
                created_folders.append(folder)

        for name, text in values:
            _write_step(
                name, _write_temporary,
                out_dir / (name + ".tmp"), text, temporary_paths,
            )

        # Every file must read back correctly before the first replacement.
        for name, text in values:
            read_back = _write_step(name, _read_text, out_dir / (name + ".tmp"))
            if read_back != text:
                raise SiteWriteError(name + ": write: read back differently")

        for name, text in values:
            _write_step(name, os.replace, out_dir / (name + ".tmp"), out_dir / name)
    except Exception:
        # Only remove files and folders this run created. Keep trying cleanup
        # if a removal fails, and preserve the original value-free error.
        for path in temporary_paths:
            try:
                path.unlink()
            except OSError:
                pass
        for folder in reversed(created_folders):
            try:
                folder.rmdir()
            except OSError:
                pass
        raise


def write_site(index, pages, out_dir, reviews=None):
    """Check and render all pages before writing and verifying temporary files."""
    asset_ids = _asset_ids(index)
    for instrument_id in asset_ids:
        if instrument_id not in pages:
            raise SiteWriteError(instrument_id + ": page: missing")
    for instrument_id in sorted(pages):
        if instrument_id not in asset_ids:
            raise SiteWriteError("pages: unexpected " + instrument_id)

    out_dir = Path(out_dir)
    _check_output_folder(out_dir, asset_ids)
    ordered_pages = [pages[instrument_id] for instrument_id in asset_ids]
    try:
        landing = render_landing(index, ordered_pages, reviews)
        values = [
            (instrument_id + "/index.html", render_page(page, index))
            for instrument_id, page in zip(asset_ids, ordered_pages)
        ]
    except Exception as error:
        message = "site: render: " + type(error).__name__
        if type(error) is SiteError:
            message += ": " + str(error)
        raise SiteWriteError(message) from None
    values.append(("index.html", landing))

    _write_values(values, asset_ids, out_dir)
    return {
        "data_as_of": index["data_as_of"],
        "headlines": [
            instrument_id for instrument_id, page in zip(asset_ids, ordered_pages)
            if page["headline"] is not None
        ],
        "written": [name for name, text in values],
    }


def _load_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def main(argv, root, out):
    """Load committed page data and return an exit code with a value-free report."""
    if argv:
        print("Usage: python3 scripts/build_site.py", file=out)
        return 2

    root = Path(root)
    data_dir = root / "site" / "data"
    try:
        index = _load_json(data_dir / "index.json")
    except Exception as error:
        print("FAILED: index: load: " + type(error).__name__, file=out)
        print("Nothing was written.", file=out)
        return 1

    try:
        asset_ids = _asset_ids(index)
    except SiteWriteError as error:
        print("FAILED: " + str(error), file=out)
        print("Nothing was written.", file=out)
        return 1

    pages = {}
    for instrument_id in asset_ids:
        try:
            pages[instrument_id] = _load_json(data_dir / (instrument_id + ".json"))
        except Exception as error:
            print("FAILED: {}: load: {}".format(
                instrument_id, type(error).__name__,
            ), file=out)
            print("Nothing was written.", file=out)
            return 1

    try:
        reviews = _load_json(root / "words" / "review_record.json")
    except Exception as error:
        print("FAILED: reviews: load: " + type(error).__name__, file=out)
        print("Nothing was written.", file=out)
        return 1

    try:
        summary = write_site(index, pages, root / "site", reviews)
        print("Pages for data as of {}: {} of {} have an approved headline.".format(
            summary["data_as_of"], len(summary["headlines"]), len(asset_ids),
        ), file=out)
        print("Wrote {} files to site.".format(len(summary["written"])), file=out)
        return 0
    except SiteWriteError as error:
        print("FAILED: " + str(error), file=out)
    except Exception as error:
        print("FAILED: unexpected {}.".format(type(error).__name__), file=out)
    print("Check git status --short before committing anything.", file=out)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], _REPO_ROOT, sys.stdout))
