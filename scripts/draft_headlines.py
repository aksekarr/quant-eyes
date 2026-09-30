"""Draft checked headline candidates from the site's published pages."""

import datetime
import json
import os
from pathlib import Path
import re
import sys


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from pipeline.providers import ProviderError
from pipeline.publish import RegistryError, check_registry
from words.cards import WordsError
from words.headline import (
    DRAFT_MODEL,
    PROMPT_VERSION,
    check_headline,
    draft_request,
    read_draft,
)


_MESSAGE_ERRORS = (RegistryError, WordsError, ProviderError)
_USAGE = "Usage: python3 scripts/draft_headlines.py [--list | <asset id> ...]"
_OPENAI_URL = "https://api.openai.com/v1/responses"
_KEY_NAME = "QX_OPENAI_API_KEY"


class _ReadBackError(Exception):
    """Identify the one value mismatch whose wording is fixed by the method."""


def _load_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _asset_ids(registry):
    return [
        instrument["id"] for instrument in registry["instruments"]
        if instrument["role"] == "asset"
    ]


def _count(count, noun):
    return "{} {}{}".format(count, noun, "" if count == 1 else "s")


def _failure(out, message, requests_sent):
    print("FAILED: " + message, file=out)
    if requests_sent:
        print(
            "Nothing was written. {} sent.".format(
                _count(requests_sent, "request")
            ),
            file=out,
        )
    else:
        print("Nothing was sent or written.", file=out)
    return 1


def _step_error(who, step, error):
    message = "{}: {}: {}".format(who, step, type(error).__name__)
    if type(error) in _MESSAGE_ERRORS:
        message += ": " + str(error)
    return message


def _arguments_are_valid(argv):
    if argv == [] or argv == ["--list"]:
        return True
    return (
        bool(argv)
        and all(isinstance(item, str) and not item.startswith("-") for item in argv)
        and len(set(argv)) == len(argv)
    )


def _write_drafts(path, value):
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        text = json.dumps(
            value,
            indent=2,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=False,
        ) + "\n"
        with temporary_path.open("w", encoding="utf-8") as temporary_file:
            temporary_file.write(text)
        if _load_json(temporary_path) != value:
            raise _ReadBackError("read back differently")
        os.replace(temporary_path, path)
    except Exception:
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise


def _problem_rules(problems):
    rules = []
    for problem in problems:
        rule = problem.split(": ", 1)[0]
        if rule not in rules:
            rules.append(rule)
    return rules


def main(argv, environ, today, root, out, post):
    """Draft selected assets, with every external dependency supplied explicitly."""
    requests_sent = 0
    try:
        if not _arguments_are_valid(argv):
            print(_USAGE, file=out)
            return 2

        root = Path(root)
        try:
            registry = _load_json(root / "pipeline" / "instruments.json")
        except Exception as error:
            return _failure(
                out,
                "registry: load: " + type(error).__name__,
                requests_sent,
            )

        try:
            check_registry(registry)
        except Exception as error:
            return _failure(
                out,
                _step_error("registry", "check", error),
                requests_sent,
            )

        all_asset_ids = _asset_ids(registry)
        list_only = argv == ["--list"]
        named_ids = [] if list_only else argv
        if named_ids:
            assets = set(all_asset_ids)
            for name in named_ids:
                if name not in assets:
                    return _failure(
                        out,
                        "{} is not an asset in the instrument list.".format(name),
                        requests_sent,
                    )
            selected = [asset_id for asset_id in all_asset_ids if asset_id in named_ids]
        else:
            selected = list(all_asset_ids)

        pages = {}
        requests = {}
        page_dates = None
        for asset_id in selected:
            try:
                page = _load_json(root / "site" / "data" / (asset_id + ".json"))
            except Exception as error:
                return _failure(
                    out,
                    "{}: load: {}".format(asset_id, type(error).__name__),
                    requests_sent,
                )

            try:
                is_this_asset = page["instrument"]["id"] == asset_id
            except Exception:
                is_this_asset = False
            if not is_this_asset:
                return _failure(
                    out,
                    "{}: page: not this asset's page".format(asset_id),
                    requests_sent,
                )

            current_dates = (page["data_as_of"], page["generated_on"])
            if page_dates is None:
                page_dates = current_dates
            elif current_dates != page_dates:
                return _failure(
                    out,
                    "{}: page: data_as_of or generated_on differs".format(asset_id),
                    requests_sent,
                )

            try:
                request = draft_request(page)
            except Exception as error:
                return _failure(
                    out,
                    _step_error(asset_id, "request", error),
                    requests_sent,
                )
            pages[asset_id] = page
            requests[asset_id] = request

        data_as_of, generated_on = page_dates
        if list_only:
            print(
                "Plan: {} to {}, one per asset: {}.".format(
                    _count(len(selected), "request"),
                    DRAFT_MODEL,
                    ", ".join(selected),
                ),
                file=out,
            )
            print(
                "Pages: data as of {}, generated on {}.".format(
                    data_as_of, generated_on
                ),
                file=out,
            )
            print("No requests made.", file=out)
            return 0

        key = environ.get(_KEY_NAME)
        if not key:
            return _failure(
                out,
                _KEY_NAME + " is not set in this terminal.",
                requests_sent,
            )
        if not isinstance(key, str) or re.fullmatch(r"[A-Za-z0-9_-]+", key) is None:
            return _failure(
                out,
                _KEY_NAME + " is not a valid key.",
                requests_sent,
            )

        headers = {
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        }
        drafts = {}
        for asset_id in selected:
            requests_sent += 1
            try:
                response = post(_OPENAI_URL, headers, requests[asset_id])
            except Exception as error:
                return _failure(
                    out,
                    _step_error(asset_id, "post", error),
                    requests_sent,
                )

            try:
                draft = read_draft(response)
            except Exception as error:
                return _failure(
                    out,
                    _step_error(asset_id, "response", error),
                    requests_sent,
                )

            try:
                problems = check_headline(
                    draft["text"], draft["claims"], pages[asset_id], registry
                )
            except Exception as error:
                return _failure(
                    out,
                    _step_error(asset_id, "check", error),
                    requests_sent,
                )
            drafts[asset_id] = {
                "text": draft["text"],
                "claims": draft["claims"],
                "drafted_by": draft["drafted_by"],
                "problems": problems,
            }

        value = {
            "data_as_of": data_as_of,
            "generated_on": generated_on,
            "drafted_on": today.isoformat(),
            "model": DRAFT_MODEL,
            "prompt_version": PROMPT_VERSION,
            "drafts": drafts,
        }
        try:
            _write_drafts(root / "words" / "headline_drafts.json", value)
        except _ReadBackError:
            return _failure(
                out,
                "drafts: write: read back differently",
                requests_sent,
            )
        except Exception as error:
            return _failure(
                out,
                _step_error("drafts", "write", error),
                requests_sent,
            )

        print(
            "Drafted {} with {} for data as of {}.".format(
                _count(len(selected), "headline"), DRAFT_MODEL, data_as_of
            ),
            file=out,
        )
        for asset_id in selected:
            rules = _problem_rules(drafts[asset_id]["problems"])
            if rules:
                print("{}: fails {}".format(asset_id, ", ".join(rules)), file=out)
            else:
                print("{}: passes the checks".format(asset_id), file=out)
        print(
            "Wrote words/headline_drafts.json. Review every draft before copying it into words/headlines.json.",
            file=out,
        )
        return 0
    except Exception as error:
        return _failure(
            out,
            "unexpected {}.".format(type(error).__name__),
            requests_sent,
        )


if __name__ == "__main__":
    from pipeline.network import http_post_json

    sys.exit(main(
        sys.argv[1:],
        os.environ,
        datetime.date.today(),
        _REPO_ROOT,
        sys.stdout,
        http_post_json,
    ))
