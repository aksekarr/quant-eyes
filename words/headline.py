"""Check drafted and approved headlines for methodology section 15."""

from copy import deepcopy
import re

from pipeline.publish import _date_from_text
from words.cards import WordsError, month_name


ADVICE_WORDS = (
    "buy", "buys", "buying", "bought", "sell", "sells", "selling", "sold",
    "should", "attractive", "cheap", "cheaper", "cheapest", "safe", "safer",
    "safest", "safety", "guarantee", "guaranteed", "guarantees", "recommend",
    "recommends", "recommended", "recommendation", "diversifier", "diversify",
    "diversifies", "diversification", "hedge", "hedges", "protect", "protects",
    "protected", "protection", "limited to",
)
FUTURE_WORDS = (
    "will", "won't", "shall", "expect", "expects", "expected", "expecting",
    "forecast", "forecasts", "predict", "predicts", "predicted", "prediction",
    "future", "likely", "could", "may", "might", "outlook", "poised", "ahead",
    "soon", "going to", "set to",
)
NUMBER_WORDS = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "million", "billion", "dozen", "twice", "thrice", "double",
    "doubled", "doubling", "triple", "tripled", "quadruple", "half", "halved",
    "halving", "quarter", "third", "percent", "per cent",
)
COMPARISON_WORDS = (
    "than", "versus", "vs", "compared", "comparison", "relative", "outperform",
    "outperformed", "outperforming", "underperform", "underperformed", "beat",
    "beats", "beating", "tracker", "benchmark", "index",
)
LOADED_WORDS = (
    "only", "just", "merely", "huge", "massive", "enormous", "extreme",
    "extremely", "dramatic", "dramatically", "stunning", "incredible",
    "impressive", "spectacular", "terrible", "disastrous", "catastrophic",
    "soared", "soaring", "plunged", "plummeted", "crashed", "skyrocketed",
    "rocketed", "collapse", "collapsed",
)
DOWN_WORDS = (
    "fall", "falls", "fell", "fallen", "falling", "drop", "drops", "dropped",
    "down", "decline", "declined", "declines", "lost", "lose", "loss", "losses",
    "below", "lower",
)
UP_WORDS = (
    "rise", "rises", "rose", "risen", "rising", "gain", "gains", "gained", "up",
    "grew", "grow", "grown", "growth", "increase", "increased", "increases",
    "higher", "above",
)

_WORD_PATTERN = re.compile(r"[a-z]+(?:'[a-z]+)*")
_BEFORE_FORBIDDEN = frozenset(".,£$€−-+/")


def _problem(rule, detail):
    return "{}: {}".format(rule, detail)


def _phrase_occurrences(text, phrase):
    """Return occurrences with section 15's exact surrounding boundaries."""
    occurrences = []
    start = 0
    while True:
        start = text.find(phrase, start)
        if start < 0:
            return occurrences
        end = start + len(phrase)
        before_ok = start == 0 or (
            not text[start - 1].isalnum()
            and text[start - 1] not in _BEFORE_FORBIDDEN
        )
        after_ok = end == len(text) or (
            not text[end].isalnum()
            and text[end] != "%"
            and not (
                text[end] in ".,"
                and end + 1 < len(text)
                and text[end + 1].isdigit()
            )
        )
        if before_ok and after_ok:
            occurrences.append((start, end))
        start += 1


def _words(text):
    """Return lower-case words plus possessive bases, in text order."""
    result = []
    for match in _WORD_PATTERN.finditer(text.lower().replace("’", "'")):
        word = match.group(0)
        result.append((match.start(), word))
        if word.endswith("'s"):
            result.append((match.start(), word[:-2]))
    result.sort(key=lambda item: item[0])
    return [word for _, word in result]


def _listed_hits(words, entries):
    singles = set(entry for entry in entries if " " not in entry)
    phrases = set(entry for entry in entries if " " in entry)
    hits = []
    for index, word in enumerate(words):
        if word in singles:
            hits.append(word)
        if index + 1 < len(words):
            phrase = word + " " + words[index + 1]
            if phrase in phrases:
                hits.append(phrase)
    return hits


def check_headline(text, claim_ids, page, registry):
    """Return all section 15.1 problems in rule order."""
    if (
        not isinstance(text, str) or not text or text != text.strip()
        or "\n" in text or "\r" in text or "\t" in text
    ):
        return [_problem("text", "headline must be trimmed single-line text")]

    claims_by_id = {claim["id"]: claim for claim in page["claims"]}
    claim_ids_valid = (
        type(claim_ids) is list
        and len(claim_ids) in (1, 2)
        and all(isinstance(item, str) for item in claim_ids)
    )
    if (
        not claim_ids_valid or len(set(claim_ids)) != len(claim_ids)
        or any(item not in claims_by_id for item in claim_ids)
    ):
        return [_problem("claims", "cite one or two different page claim ids")]
    cited = [claims_by_id[claim_id] for claim_id in claim_ids]
    problems = []

    for claim in cited:
        if claim.get("series") != "asset" or claim.get("kind") != "observed":
            problems.append(_problem("citable", "{} is not the asset's observed history".format(claim["id"])))

    sentence_ok = text.endswith(".")
    for index, character in enumerate(text[:-1]):
        if character in "!?;":
            sentence_ok = False
        elif character == "." and not (
            index > 0 and text[index - 1].isdigit()
            and index + 1 < len(text) and text[index + 1].isdigit()
        ):
            sentence_ok = False
    if not sentence_ok:
        problems.append(_problem("one_sentence", "use one full-stop-terminated sentence"))
    if len(text.split()) > 30:
        problems.append(_problem("length", "headline has more than 30 words"))

    allowed = []
    for claim in cited:
        allowed.extend((
            claim["display"], month_name(claim["period_start"]),
            month_name(claim["period_end"]),
        ))
        if claim["id"].startswith("worst.ten_thousand"):
            allowed.append("£10,000")
        if "rate_shock" in claim["id"]:
            allowed.append("2022 rate shock")

    covered = [False] * len(text)
    for phrase in sorted(set(allowed), key=lambda item: (-len(item), item)):
        for start, end in _phrase_occurrences(text, phrase):
            if not any(covered[start:end]):
                covered[start:end] = [True] * (end - start)

    uncited = []
    for index, character in enumerate(text):
        if not covered[index] and (character.isdigit() or character in "%£$€"):
            uncited.append(character)
    if uncited:
        problems.append(_problem("uncited_number", "headline contains an uncited figure"))
    for claim in cited:
        if not _phrase_occurrences(text, claim["display"]):
            problems.append(_problem("display_missing", "{} display is missing".format(claim["id"])))

    uncovered_text = "".join(" " if covered[index] else character for index, character in enumerate(text))
    words = _words(uncovered_text)
    for rule, entries in (
        ("advice", ADVICE_WORDS),
        ("future", FUTURE_WORDS),
        ("number_word", NUMBER_WORDS),
        ("comparison", COMPARISON_WORDS),
        ("loaded", LOADED_WORDS),
    ):
        hits = _listed_hits(words, entries)
        if rule == "number_word":
            hits.extend(word for word in words if len(word) > 4 and word.endswith("fold"))
        for hit in hits:
            problems.append(_problem(rule, "contains {}".format(hit)))

    own_id = page["instrument"]["id"]
    other_hits = []
    for instrument in registry["instruments"]:
        if instrument["id"] == own_id:
            continue
        for name in (
            instrument["label"], instrument["identity"]["name"],
            instrument["identity"]["ticker"],
        ):
            pattern = re.compile(
                r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])".format(re.escape(name)),
                re.IGNORECASE,
            )
            for match in pattern.finditer(text):
                other_hits.append((match.start(), name))
    for _, name in sorted(other_hits):
        problems.append(_problem("other_instrument", "names {}".format(name)))

    word_set = set(words)
    for claim in cited:
        direction = claim.get("direction")
        needed = DOWN_WORDS if direction == "down" else UP_WORDS if direction == "up" else ()
        if needed and not word_set.intersection(needed):
            problems.append(_problem("direction", "{} lacks a {} word".format(claim["id"], direction)))
    return problems


def _approval_keys(value, expected, part):
    if type(value) is not dict or set(value) != set(expected):
        raise WordsError("{} must contain exactly {}.".format(part, ", ".join(expected)))


def check_approvals(approvals, pages, registry):
    """Return current, checked approvals in the instrument list's order."""
    _approval_keys(approvals, ("data_as_of", "headlines"), "approvals")
    try:
        month_name(approvals["data_as_of"])
    except ValueError:
        raise WordsError("data_as_of must be a valid YYYY-MM month.") from None
    headlines = approvals["headlines"]
    if type(headlines) is not dict:
        raise WordsError("headlines must be a dictionary.")

    assets = {
        instrument["id"]: instrument for instrument in registry["instruments"]
        if instrument["role"] == "asset"
    }
    for asset_id, headline in headlines.items():
        if asset_id not in assets:
            raise WordsError("{} is not an asset in the registry.".format(asset_id))
        _approval_keys(
            headline, ("text", "claims", "drafted_by", "reviewed_on"), asset_id,
        )
        if not isinstance(headline["drafted_by"], str) or not headline["drafted_by"].strip():
            raise WordsError("{} drafted_by must be non-empty text.".format(asset_id))
        _date_from_text(headline["reviewed_on"], "{} reviewed_on".format(asset_id), WordsError)

    if any(page.get("data_as_of") != approvals["data_as_of"] for page in pages):
        return {}

    pages_by_id = {}
    for page in pages:
        asset_id = page["instrument"]["id"]
        pages_by_id.setdefault(asset_id, []).append(page)

    result = {}
    for asset_id in assets:
        if asset_id not in headlines:
            continue
        matching_pages = pages_by_id.get(asset_id, [])
        if len(matching_pages) != 1:
            raise WordsError("{} must have exactly one page.".format(asset_id))
        page = matching_pages[0]
        headline = headlines[asset_id]
        reviewed = _date_from_text(
            headline["reviewed_on"], "{} reviewed_on".format(asset_id), WordsError,
        )
        generated = _date_from_text(
            page["generated_on"], "{} generated_on".format(asset_id), WordsError,
        )
        if reviewed < generated:
            raise WordsError("{} reviewed_on is before generated_on.".format(asset_id))
        problems = check_headline(
            headline["text"], headline["claims"], page, registry,
        )
        if problems:
            rules = []
            for problem in problems:
                rule = problem.split(": ", 1)[0]
                if rule not in rules:
                    rules.append(rule)
            raise WordsError("{} headline failed: {}.".format(asset_id, ", ".join(rules)))
        result[asset_id] = deepcopy(headline)
    return result
