"""Check drafted and approved headlines for methodology section 15."""

from copy import deepcopy
import json
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
    "rocketed", "collapse", "collapsed", "never",
    "largest", "biggest", "worst", "deepest", "steepest", "sharpest",
    "greatest", "highest", "lowest", "record", "ever", "all time",
)
RECOVERY_WORDS = (
    "recover", "recovers", "recovered", "recovering", "recovery", "regain",
    "regains", "regained", "regaining", "back",
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

DRAFT_MODEL = "gpt-6.1-sol"
PROMPT_VERSION = "3"

_DRAFT_INSTRUCTIONS_TEMPLATE = """You write the headline for one page of a website that explains, in plain English, how one investment behaved in the past. Its readers are UK investors. The page describes history and never gives advice. Code checks your headline, and then a person reviews it before it is published.

Write one sentence that gives the gist of what holding this investment was like, using one or two of the figures you are given. Return the sentence as "text" and the ids of the figures it uses as "claims".

Rules:
1. One sentence in the past tense, at most 30 words, ending with a full stop. No semicolons, question marks or exclamation marks.
2. Cite one or two figures, and write every figure you cite exactly as given, such as 35.5% or £6,450. Put no plus or minus sign in front of a figure: say the direction in words.
3. If the input says the investment trades in US dollars, write "in pounds" in the sentence: every figure is in pounds, and a fall in pounds can be very different from the same fall in dollars.
4. Use no other numbers. The only exceptions: the first and last months of a cited figure's period, written exactly as given (Feb 2009, never February 2009); £10,000 when citing a figure about £10,000 invested; and "2022 rate shock" when citing that period's figure.
5. If a cited figure's direction is down, use one of these words: {down}. If it is up, use one of these: {up}.
6. Describe this investment alone. Do not compare it with anything, and do not name any other investment, fund, index or tracker.
7. Do not rank a fall. The data starts at a fixed month, so a fall can't be called the largest, worst or deepest. Say when it happened instead, using its first and last months.
8. Words about recovery ({recovery}) must agree with the page. If its largest fall had not recovered, put "not" just before them, as in "had not recovered". If it recovered, never negate them. If it had not fallen below a previous high, do not use them.
9. Never use these words or phrases:
- advice: {advice}
- the future: {future}
- numbers in words: {number}, or any word ending in "fold"
- comparisons: {comparison}
- loaded words: {loaded}"""

DRAFT_INSTRUCTIONS = _DRAFT_INSTRUCTIONS_TEMPLATE.format(
    down=", ".join(DOWN_WORDS),
    up=", ".join(UP_WORDS),
    recovery=", ".join(RECOVERY_WORDS),
    advice=", ".join(ADVICE_WORDS),
    future=", ".join(FUTURE_WORDS),
    number=", ".join(NUMBER_WORDS),
    comparison=", ".join(COMPARISON_WORDS),
    loaded=", ".join(LOADED_WORDS),
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


def _word_runs(text):
    """Return each lower-case run of letters, with internal apostrophes, once."""
    return [
        match.group(0)
        for match in _WORD_PATTERN.finditer(text.lower().replace("’", "'"))
    ]


def _words(text):
    """Return lower-case words plus possessive bases, in text order."""
    result = []
    for position, word in enumerate(_word_runs(text)):
        result.append((position, word))
        if word.endswith("'s"):
            result.append((position, word[:-2]))
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


def _recovery_state(page):
    """Return section 15's recovery state from all claims on the page."""
    page_claim_ids = {claim["id"] for claim in page["claims"]}
    if "worst.below_high_at_end" in page_claim_ids:
        return "not recovered"
    if "worst.months_to_recover" in page_claim_ids:
        return "recovered"
    return "no fall"


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

    recovery_words = _word_runs(uncovered_text)
    recovery_state = _recovery_state(page)
    for index, word in enumerate(recovery_words):
        if word not in RECOVERY_WORDS:
            continue
        preceding = recovery_words[max(0, index - 2):index]
        negated = any(item == "not" or item.endswith("n't") for item in preceding)
        wrong = (
            recovery_state == "no fall"
            or (recovery_state == "not recovered" and not negated)
            or (recovery_state == "recovered" and negated)
        )
        if wrong:
            problems.append(_problem(
                "recovery", "{} conflicts with {}".format(word, recovery_state),
            ))

    trades_in_dollars = any(
        instrument["id"] == own_id
        and instrument["identity"]["trading_currency"] == "USD"
        for instrument in registry["instruments"]
    )
    if trades_in_dollars:
        currency_phrases = {"GBP": "in pounds", "USD": "in dollars"}
        for claim in cited:
            phrase = currency_phrases.get(claim.get("currency"))
            if phrase is not None and not _listed_hits(words, (phrase,)):
                problems.append(_problem(
                    "currency", "{} needs {}".format(claim["id"], phrase),
                ))
    return problems


def draft_request(page):
    """Build one section 15.3 Responses API request from a page."""
    claims_by_id = {claim["id"]: claim for claim in page["claims"]}
    offered_cards = []
    offered_claims = []
    offered_ids = set()

    for card in page["cards"]:
        if card["id"] not in ("bumpy", "worst", "panic"):
            continue
        offered_sentences = []
        for sentence in card["sentences"]:
            claim_ids = sentence["claims"]
            for claim_id in claim_ids:
                if claim_id not in claims_by_id:
                    raise WordsError(
                        "{} is not a claim on the page.".format(claim_id)
                    )
            if not claim_ids:
                continue
            claims = [claims_by_id[claim_id] for claim_id in claim_ids]
            if not all(
                claim.get("series") == "asset"
                and claim.get("kind") == "observed"
                for claim in claims
            ):
                continue
            offered_sentences.append(sentence["text"])
            for claim in claims:
                if claim["id"] == "worst.months_to_recover":
                    continue
                if claim["id"] not in offered_ids:
                    offered_ids.add(claim["id"])
                    offered_claims.append(claim)
        if offered_sentences:
            offered_cards.append((card["title"], offered_sentences))

    if not offered_claims:
        raise WordsError("page has no figures to cite.")

    instrument = page["instrument"]
    lines = [
        "Investment: " + instrument["label"],
        "Full name: " + instrument["identity"]["name"],
        "Ticker: " + instrument["identity"]["ticker"],
    ]
    if instrument["identity"]["trading_currency"] == "USD":
        lines.append("Every figure here is in pounds, but it trades in US dollars.")
    lines.extend((
        page["data_as_of_text"] + ".",
        "",
        "What its page says:",
    ))
    for title, sentences in offered_cards:
        lines.append(title)
        lines.extend("- " + sentence for sentence in sentences)

    lines.extend((
        "",
        "Figures you may cite (id | figure | direction | period):",
    ))
    for claim in offered_claims:
        lines.append("{} | {} | {} | {} to {}".format(
            claim["id"],
            claim["display"],
            claim.get("direction") or "none",
            month_name(claim["period_start"]),
            month_name(claim["period_end"]),
        ))

    recovery_lines = {
        "not recovered": "Its largest fall had not recovered by the end of the data.",
        "recovered": "Its largest fall recovered.",
        "no fall": "It had not fallen below a previous high at any month-end.",
    }
    lines.extend(("", recovery_lines[_recovery_state(page)]))

    schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "claims": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [claim["id"] for claim in offered_claims],
                },
            },
        },
        "required": ["text", "claims"],
        "additionalProperties": False,
    }
    return {
        "model": DRAFT_MODEL,
        "instructions": DRAFT_INSTRUCTIONS,
        "input": "\n".join(lines),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "headline",
                "strict": True,
                "schema": schema,
            },
        },
        "reasoning": {"effort": "medium"},
        "max_output_tokens": 8000,
        "store": False,
    }


def _identifier(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 64
        and all(character in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in value)
    )


def read_draft(response):
    """Read one section 15.3 response without exposing response contents."""
    if type(response) is not dict:
        raise WordsError("response is not an object")

    status = response.get("status")
    if status != "completed":
        message = "status " + (status if _identifier(status) else "unreadable")
        reason = None
        incomplete = response.get("incomplete_details")
        if type(incomplete) is dict and _identifier(incomplete.get("reason")):
            reason = incomplete["reason"]
        error = response.get("error")
        if reason is None and type(error) is dict and _identifier(error.get("code")):
            reason = error["code"]
        if reason is not None:
            message += " ({})".format(reason)
        raise WordsError(message)

    model = response.get("model")
    if not isinstance(model, str) or not model or model != model.strip():
        raise WordsError("model missing")

    output = response.get("output")
    if type(output) is not list:
        raise WordsError("output missing")
    answers = [
        item for item in output
        if type(item) is dict
        and item.get("type") == "message"
        and item.get("phase") != "commentary"
    ]
    if len(answers) != 1:
        raise WordsError("{} answers".format(len(answers)))

    content = answers[0].get("content")
    if type(content) is not list or not content:
        raise WordsError("answer has no content")
    if any(
        type(item) is dict and item.get("type") == "refusal"
        for item in content
    ):
        raise WordsError("the model refused")
    if not all(
        type(item) is dict
        and item.get("type") == "output_text"
        and isinstance(item.get("text"), str)
        for item in content
    ):
        raise WordsError("unexpected content")

    answer_text = "".join(item["text"] for item in content)
    try:
        headline = json.loads(answer_text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise WordsError("answer is not a headline object") from None
    if type(headline) is not dict or set(headline) != {"text", "claims"}:
        raise WordsError("answer is not a headline object")
    return {
        "text": headline["text"],
        "claims": headline["claims"],
        "drafted_by": model,
    }


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
