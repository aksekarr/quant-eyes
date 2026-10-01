"""Render section 16's checked page data to HTML strings, without I/O."""

import datetime
import html
import math
import re


SITE_NAME = "Quant Eyes"
HEADLINE_RULE_COUNT = 16

_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_COUNTS = "one two three four five six seven eight nine ten eleven twelve".split()
_TRAIL_RULES = (
    "Plain text, nothing blank",
    "Cites 1 or 2 figures from its page",
    "Only the investment's own past",
    "One sentence, no questions",
    "30 words or fewer",
    "Every number is a cited figure",
    "Figures exactly as the page shows",
    "No advice words",
    "No predictions",
    "Numbers as figures, not words",
    "No comparisons",
    "No ranking or loaded words",
    "Names no other investment",
    "A fall is called a fall",
    "Recovery words match the facts",
    '"in pounds" or "in dollars" said',
)
_CARD_IDS = ("bumpy", "worst", "panic", "next", "pound", "limits")
_WINDOWS = ("gfc", "covid", "rate_shock")
_TYPES = {
    "share": "Share",
    "etf": "Exchange-traded fund",
    "etc": "Exchange-traded commodity",
    "cryptocurrency": "Cryptocurrency",
}
_SHARED_KEYS = ("data_as_of", "data_as_of_text", "generated_on", "method_version")
_TAGLINE = (
    "How one more investment has behaved, and what it did next to a developed-world "
    "tracker. In plain English, in pounds."
)
_DISCLAIMER = (
    "Past results in pounds, measured at month-ends. Descriptive, never advice. "
    "Past behaviour does not predict future results."
)
_METHODS = {
    "bumpy": (
        "A month's return is the change in value from one month-end to the next, in "
        "pounds, with any income reinvested. Volatility is the standard deviation of "
        "those monthly returns (the sample version, dividing by one fewer than the "
        "number of months), multiplied by √12 to make it a yearly figure. That step "
        "treats months as independent, which is an approximation."
    ),
    "worst": (
        "At each month-end the value is compared with the highest month-end value so "
        "far. The largest fall is the deepest drop below that high; if two are equally "
        "deep, the earlier counts. The first month in the data counts as a high, so a "
        "fall that began earlier is measured only from there. The high is the last "
        "month-end at that level before the low; back at the high is the first "
        "month-end at or above it. Months are counted between month-ends. The £10,000 "
        "figure is £10,000 × (1 − the fall), rounded to the nearest £10."
    ),
    "panic": (
        "Each window runs from the month-end before it starts to the month-end it "
        "finishes: the 2022 rate shock runs from the end of Dec 2021 to the end of "
        "Oct 2022. The figure is the change between those two month-ends, not the "
        "largest fall inside the window. A window is shown only if the data covers "
        "both month-ends; it is never shortened to fit."
    ),
    "next": (
        "Correlation is the Pearson correlation of the two sets of monthly returns "
        "in pounds, over the months both cover. The 36-month range repeats it for "
        "every run of 36 consecutive months and shows the lowest and highest. The "
        "90/10 mix starts at 90% tracker and 10% this investment; each part grows or "
        "shrinks with its own returns, and at the end of every December the mix is "
        "reset to 90/10. A yearly figure is the total return turned into a compound "
        "rate: (1 + total return)^(12 ÷ months) − 1. Before fees, with no trading "
        "costs or tax."
    ),
}
_TABLE_LABELS = {
    "bumpy.volatility": "Volatility, a year",
    "bumpy.volatility_common": "Same months as the tracker",
    "bumpy.tracker_volatility": "The tracker, same months",
    "worst.months_to_low": "High to low",
    "worst.ten_thousand_left": "£10,000 at the high, worth at the low",
    "worst.ten_thousand_lost": "£10,000 at the high, less at the low",
    "worst.months_to_recover": "Low to back at the high",
    "worst.months_underwater": "Time below the high",
    "worst.below_high_at_end": "Still below its high at the end",
}


class SiteError(Exception):
    """Page data cannot be rendered under section 16's contract."""


def _nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def _url(value):
    return isinstance(value, str) and value.startswith("https://") and not re.search(r"\s", value)


def _check_index(index):
    for key in ("assets", "benchmark") + _SHARED_KEYS:
        if key not in index:
            raise SiteError("index: missing " + key)
    assets = index["assets"]
    if not isinstance(assets, list) or not 2 <= len(assets) <= 12:
        raise SiteError("index: assets: count")
    for asset in assets:
        for field in ("id", "label", "name", "ticker", "type"):
            if not isinstance(asset, dict) or not _nonblank(asset.get(field)):
                raise SiteError("index: assets: missing " + field)
    ids = set()
    for asset in assets:
        if asset["id"] in ids:
            raise SiteError("index: assets: duplicate " + asset["id"])
        ids.add(asset["id"])


def _check_page(page, index):
    """Validate in the specified order, returning a local claim lookup."""
    for key in ("instrument", "benchmark") + _SHARED_KEYS + (
        "sources", "cards", "claims", "headline"
    ):
        if key not in page:
            raise SiteError("page: missing " + key)
    instrument = page["instrument"]
    asset_id = instrument["id"]
    prefix = asset_id + ": "
    entry = next((a for a in index["assets"] if a["id"] == asset_id), None)
    if entry is None:
        raise SiteError(prefix + "not in the index")
    for key in _SHARED_KEYS:
        if page[key] != index[key]:
            raise SiteError(prefix + key + " differs from the index")
    identity = instrument["identity"]
    for key, value in (("label", instrument["label"]), ("name", identity["name"]),
                       ("ticker", identity["ticker"])):
        if value != entry[key]:
            raise SiteError(prefix + key + " differs from the index")
    if identity.get("type") not in _TYPES:
        raise SiteError(prefix + "identity: type")
    if identity.get("trading_currency") not in ("USD", "GBP"):
        raise SiteError(prefix + "identity: trading_currency")
    if any(not _url(url) for url in identity["sources"]):
        raise SiteError(prefix + "identity: sources")
    for source in page["sources"]:
        if not isinstance(source, dict) or not _nonblank(source.get("provider")):
            raise SiteError(prefix + "sources: provider")
        if not _url(source.get("url")):
            raise SiteError(prefix + "sources: url")
        labels = source.get("used_for")
        if not isinstance(labels, list) or not labels or not all(map(_nonblank, labels)):
            raise SiteError(prefix + "sources: used_for")
    cards = page["cards"]
    if (not isinstance(cards, list) or any(not isinstance(c, dict) for c in cards)
            or [c.get("id") for c in cards] != list(_CARD_IDS)):
        raise SiteError(prefix + "cards: order")
    for card in cards:
        sentences = card.get("sentences")
        if (not _nonblank(card.get("title")) or not isinstance(sentences, list)
                or not sentences or any(
                    not isinstance(s, dict) or not _nonblank(s.get("text"))
                    for s in sentences
                )):
            raise SiteError(prefix + "cards: " + card["id"])
    claims = {}
    for claim in page["claims"]:
        claim_id = claim["id"]
        if claim_id in claims:
            raise SiteError(prefix + "claims: duplicate " + claim_id)
        claims[claim_id] = claim
    if len(cards[0]["sentences"]) != 3:
        raise SiteError(prefix + "bumpy: sentences")
    for claim_id in ("bumpy.volatility", "bumpy.tracker_volatility"):
        if claim_id not in claims:
            raise SiteError(prefix + "claims: missing " + claim_id)
    own = claims.get("bumpy.volatility_common", claims["bumpy.volatility"])
    tracker = claims["bumpy.tracker_volatility"]
    if any(own[key] != tracker[key] for key in ("period_start", "period_end")):
        raise SiteError(prefix + "bumpy: periods differ")
    fall = "worst.fall" in claims
    if fall:
        required = ("worst.months_to_low", "worst.ten_thousand_left",
                    "worst.ten_thousand_lost", "worst.months_underwater")
        recovery_count = sum(key in claims for key in (
            "worst.months_to_recover", "worst.below_high_at_end"
        ))
        if any(key not in claims for key in required) or recovery_count != 1:
            raise SiteError(prefix + "worst: claims")
    elif any(key.startswith("worst.") for key in claims):
        raise SiteError(prefix + "worst: claims")
    if len(cards[1]["sentences"]) != (4 if fall else 1):
        raise SiteError(prefix + "worst: sentences")
    if len(cards[2]["sentences"]) != 7:
        raise SiteError(prefix + "panic: sentences")
    for window in _WINDOWS:
        for claim_id in ("panic." + window, "panic." + window + ".tracker"):
            if claim_id in claims and claims[claim_id].get("direction") not in ("up", "down", "flat"):
                raise SiteError(prefix + "claims: direction " + claim_id)
    for claim_id in ("next.correlation", "next.rolling_lowest", "next.rolling_highest"):
        if claim_id not in claims:
            raise SiteError(prefix + "claims: missing " + claim_id)
    if len(cards[3]["sentences"]) not in (6, 7):
        raise SiteError(prefix + "next: sentences")
    headline = page["headline"]
    if headline is not None:
        if not isinstance(headline, dict):
            raise SiteError(prefix + "headline: shape")
        for field in ("text", "drafted_by"):
            if not _nonblank(headline.get(field)):
                raise SiteError(prefix + "headline: " + field)
        reviewed = headline.get("reviewed_on")
        if not isinstance(reviewed, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", reviewed):
            raise SiteError(prefix + "headline: reviewed_on")
        try:
            datetime.date.fromisoformat(reviewed)
        except ValueError:
            raise SiteError(prefix + "headline: reviewed_on") from None
    return claims


def _check_guided(page):
    """Check optional section 18 explanations before rendering any markup."""
    guided = page["guided"]
    prefix = page["instrument"]["id"] + ": guided: "
    if (not isinstance(guided, dict) or set(guided) != {"steps"}
            or not isinstance(guided["steps"], list)):
        raise SiteError(prefix + "unreadable")
    for step in guided["steps"]:
        if (not isinstance(step, dict) or set(step) != {"card", "everyday", "more"}
                or not _nonblank(step["everyday"])
                or not isinstance(step["more"], list)
                or not 1 <= len(step["more"]) <= 6):
            raise SiteError(prefix + "unreadable")
        for panel in step["more"]:
            if (not isinstance(panel, dict) or set(panel) != {"title", "text"}
                    or not _nonblank(panel["title"]) or not _nonblank(panel["text"])):
                raise SiteError(prefix + "unreadable")
    if [step["card"] for step in guided["steps"]] != [card["id"] for card in page["cards"]]:
        raise SiteError(prefix + "cards differ")
    return guided["steps"]


def _month(value):
    year, month = value.split("-")
    return _MONTHS[int(month) - 1] + " " + year


def _period(claim):
    return _month(claim["period_start"]) + " to " + _month(claim["period_end"])


def _day(value):
    date = datetime.date.fromisoformat(value)
    return "{} {} {}".format(date.day, _MONTHS[date.month - 1], value[:4])


class _Markup:
    """Keep escaping and the data-qx text contract at one output boundary."""

    def __init__(self):
        self.parts = ["<!doctype html>"]

    def start(self, tag, attrs=None):
        attributes = "".join(
            " " + name if value is None else ' {}="{}"'.format(name, html.escape(value, quote=True))
            for name, value in (attrs or {}).items()
        )
        self.parts.append("<" + tag + attributes + ">")

    def end(self, tag):
        self.parts.append("</" + tag + ">")

    def text(self, role, text, key="", tag="p", attrs=None, text_attr=None):
        attributes = {"data-qx": role}
        if key:
            attributes["data-qx-key"] = key
        if text_attr:
            attributes["data-qx-attr"] = text_attr
            attributes[text_attr] = text
        attributes.update(attrs or {})
        self.start(tag, attributes)
        if not text_attr:
            escaped = html.escape(text, quote=True)
            if role == "figure":
                escaped = '<span data-layout="figure-text">' + escaped + '</span>'
            self.parts[-1] += escaped
        if tag not in ("meta", "input", "link", "br"):
            self.parts[-1] += "</" + tag + ">"

    def size(self, asset_id, key, calculate):
        try:
            value = calculate()
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError
            size = format(float(value), ".4f")
        except (TypeError, ValueError, OverflowError, ZeroDivisionError):
            raise SiteError(asset_id + ": size: " + key) from None
        self.text("size", "", key, tag="span", attrs={"style": "--qx-size:" + size})

    def finish(self):
        return "\n".join(self.parts) + "\n"


def _head(out, title, description, prefix):
    out.start("html", {"lang": "en-GB"})
    out.start("head")
    out.start("meta", {"charset": "utf-8"})
    out.start("meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"})
    out.text("title", title, tag="title")
    out.text("description", description, tag="meta", attrs={"name": "description"}, text_attr="content")
    out.text("og-title", title, tag="meta", attrs={"property": "og:title"}, text_attr="content")
    out.text("og-description", description, tag="meta", attrs={"property": "og:description"}, text_attr="content")
    out.start("meta", {"property": "og:type", "content": "website"})
    out.start("link", {"rel": "stylesheet", "href": prefix + "assets/site.css"})
    out.start("link", {"rel": "icon", "type": "image/svg+xml",
                       "href": prefix + "assets/brand/favicon.svg"})
    out.start("script", {"src": prefix + "assets/site.js", "defer": None})
    out.end("script")
    out.end("head")
    out.start("body")
    out.start("header")
    out.text("site-name", SITE_NAME, tag="a", attrs={"href": prefix or "./"})
    out.text("not-advice", "Not advice")
    out.end("header")


def _source_text(source):
    return source["provider"] + " (" + ", ".join(source["used_for"]) + ")"


def _footer(out, data, sources, identity=None):
    out.start("footer")
    out.text("footer-data", data["data_as_of_text"] + " · Method " + data["method_version"])
    out.start("div", {"data-layout": "sources"})
    out.text("sources-label", "Sources")
    for source in sources:
        out.text("source", _source_text(source), source["provider"], tag="a", attrs={"href": source["url"]})
    out.end("div")
    if identity is not None:
        name = identity["name"]
        if identity["isin"]:
            name += " · ISIN " + identity["isin"]
        out.text("identity", name)
        if identity["sources"]:
            out.start("div", {"data-layout": "identity-sources"})
            out.text("identity-label", "Identity from")
            for i, url in enumerate(identity["sources"], 1):
                out.text("identity-source", url[len("https://"):].split("/", 1)[0], str(i),
                         tag="a", attrs={"href": url})
            out.end("div")
    out.text("disclaimer", _DISCLAIMER)
    out.end("footer")
    out.end("body")
    out.end("html")


def _sentences(out, card, start=0, stop=None):
    if stop is None:
        stop = len(card["sentences"])
    for i in range(start, stop):
        out.text("sentence", card["sentences"][i]["text"], card["id"] + "." + str(i))


def _card_sources(page, card_id):
    own = page["instrument"]["label"]
    tracker = page["benchmark"]["label"]
    needed = {own}
    if any(c["id"].startswith(card_id + ".") and c["series"] in ("tracker", "mix")
           for c in page["claims"]):
        needed.add(tracker)
    if page["instrument"]["identity"]["trading_currency"] == "USD":
        needed.update(label for source in page["sources"] for label in source["used_for"]
                      if label not in (own, tracker))
    sources = []
    for source in page["sources"]:
        labels = [label for label in source["used_for"] if label in needed]
        if labels:
            sources.append(_source_text({"provider": source["provider"], "used_for": labels}))
    return (("Source: " if len(sources) == 1 else "Sources: ") + "; ".join(sources)
            + ". Method " + page["method_version"] + ".")


def _maths(out, page, card_id, claims):
    out.start("details")
    out.start("summary")
    out.text("maths-show", "Show the maths", card_id, tag="span")
    out.text("maths-hide", "Hide the maths", card_id, tag="span", attrs={"hidden": None})
    out.end("summary")
    out.text("maths-method", _METHODS[card_id], card_id)
    rows = [c for c in page["claims"] if c["id"].startswith(card_id + ".")]
    if card_id in ("bumpy", "worst") and rows:
        out.start("table")
        out.start("thead")
        out.start("tr")
        for key, label in (("figure", "Figure"), ("value", "Value"), ("period", "Period")):
            out.text("maths-head", label, card_id + "." + key, tag="th", attrs={"scope": "col"})
        out.end("tr")
        out.end("thead")
        out.start("tbody")
        for claim in rows:
            key = claim["id"]
            if key == "worst.fall":
                label = "Largest fall since " + _month(claims["bumpy.volatility"]["period_start"])
            else:
                label = _TABLE_LABELS[key]
            out.start("tr")
            out.text("maths-figure", label, key, tag="th", attrs={"scope": "row"})
            out.text("maths-value", claim["display"], key, tag="td")
            out.text("maths-period", _period(claim), key, tag="td")
            out.end("tr")
        out.end("tbody")
        out.end("table")
    out.text("maths-note", "Periods run from month-end to month-end. Each figure is rounded once, "
             "from the unrounded calculation.", card_id)
    out.text("maths-sources", _card_sources(page, card_id), card_id)
    out.end("details")


def _guided(out, step):
    card_id = step["card"]
    out.start("details", {"data-layout": "guided"})
    out.start("summary")
    out.text("more-open", "Explain further", card_id, tag="span")
    out.end("summary")
    out.start("div", {"data-layout": "guided-everyday"})
    out.text("everyday-label", "In everyday terms", card_id)
    out.text("everyday", step["everyday"], card_id)
    out.end("div")
    out.start("div", {"data-layout": "guided-panels"})
    for number, panel in enumerate(step["more"], 1):
        key = card_id + "." + str(number)
        out.start("div", {"data-layout": "guided-panel"})
        out.text("more-number", format(number, "02d"), key)
        out.text("more-title", panel["title"], key, tag="h3")
        out.text("more-text", panel["text"], key)
        out.end("div")
    out.end("div")
    out.end("details")


def _guided_controls(out, cards):
    labels = {
        "bumpy": "Bumpy", "worst": "Worst fall", "panic": "Panics",
        "next": "Next to tracker", "pound": "The pound", "limits": "Limits",
    }
    out.start("nav", {"data-layout": "guided-controls", "hidden": None})
    out.start("div", {"data-layout": "guided-mode"})
    out.text("mode-guided", "Guided", tag="button",
             attrs={"type": "button", "aria-pressed": "false"})
    out.text("mode-full", "Full page", tag="button",
             attrs={"type": "button", "aria-pressed": "true"})
    out.end("div")
    out.start("div", {"data-layout": "guided-track"})
    out.text("step-back", "Back", tag="button", attrs={"type": "button"})
    out.start("ol", {"data-layout": "guided-steps"})
    for number, card in enumerate(cards, 1):
        card_id = card["id"]
        out.start("li", {"data-layout": "guided-step"})
        out.text("step-node", "Step {}: {}".format(number, card["title"]),
                 card_id, tag="button", text_attr="aria-label",
                 attrs={"type": "button", "data-step": card_id})
        out.text("step-label", labels[card_id], card_id, tag="span")
        out.end("li")
    out.end("ol")
    out.text("step-next", "Next", tag="button", attrs={"type": "button"})
    out.end("div")
    out.end("nav")


def _bumpy(out, page, card, claims):
    asset_id = page["instrument"]["id"]
    out.start("div", {"data-layout": "card-lead"})
    out.start("div", {"data-layout": "lead-copy"})
    out.text("figure", claims["bumpy.volatility"]["display"], "bumpy.volatility")
    _sentences(out, card, 0, 1)
    out.end("div")
    own = claims.get("bumpy.volatility_common", claims["bumpy.volatility"])
    tracker = claims["bumpy.tracker_volatility"]
    out.start("div", {"data-layout": "bars"})
    out.start("div", {"data-layout": "bar-visual"})
    out.text("bars-label", "Same months: " + _period(own))
    for key, claim, label in (("bumpy.asset", own, page["instrument"]["label"]),
                              ("bumpy.tracker", tracker, page["benchmark"]["label"])):
        out.start("div", {"data-layout": "bar"})
        out.text("bar-label", label, key)
        out.text("bar-value", claim["display"], key)
        out.start("div", {"data-layout": "bar-track"})
        out.size(asset_id, key, lambda: claim["value"] / max(own["value"], tracker["value"]))
        out.end("div")
        out.end("div")
    out.end("div")
    _sentences(out, card, 1, 2)
    out.end("div")
    out.end("div")
    _sentences(out, card, 2)


def _worst(out, page, card, claims):
    if "worst.fall" not in claims:
        _sentences(out, card)
        return
    asset_id = page["instrument"]["id"]
    fall = claims["worst.fall"]
    left = claims["worst.ten_thousand_left"]
    low = claims["worst.months_to_low"]
    under = claims["worst.months_underwater"]
    recovery = claims.get("worst.months_to_recover")
    out.start("div", {"data-layout": "card-lead"})
    out.start("div", {"data-layout": "lead-copy"})
    out.text("figure", fall["display"], "worst.fall")
    _sentences(out, card, 0, 1)
    out.end("div")
    out.start("div", {"data-layout": "drain"})
    out.text("drain-label", "£10,000 invested at the high")
    out.text("figure", left["display"], "worst.ten_thousand_left", attrs={"data-qx-from": "10000"})
    out.text("drain-period", _period(fall))
    out.start("div", {"data-layout": "drain-track"})
    out.size(asset_id, "worst.drain", lambda: left["value"] / 10000)
    out.end("div")
    out.text("drain-left", left["display"] + " at the low")
    out.text("drain-lost", claims["worst.ten_thousand_lost"]["display"] + " less")
    out.end("div")
    out.end("div")
    out.start("div", {"data-layout": "timeline"})
    if recovery is not None:
        out.text("timeline-label", "High to back at the high: " + under["display"])
    else:
        out.text("timeline-label", "Below its high: " + under["display"]
                 + ", to the end of " + _month(under["period_end"]))
    out.start("div", {"data-layout": "timeline-container"})
    out.start("div", {"data-layout": "timeline-track"})
    out.text("segment", low["display"], "worst.fall")
    out.size(asset_id, "worst.fall", lambda: low["value"] / under["value"])
    if recovery is not None:
        out.text("segment", recovery["display"], "worst.recovery")
        out.size(asset_id, "worst.recovery", lambda: recovery["value"] / under["value"])
        end_point = ("back", "Back at the high", recovery["period_end"])
    else:
        out.text("segment", "still " + claims["worst.below_high_at_end"]["display"]
                 + " below its high", "worst.since-low")
        out.size(asset_id, "worst.since-low", lambda: (under["value"] - low["value"]) / under["value"])
        end_point = ("end", "Not recovered by", under["period_end"])
    for key, label, month in (("high", "High", fall["period_start"]),
                               ("low", "Low", fall["period_end"]), end_point):
        out.start("div", {"data-layout": "timeline-point", "data-point": key})
        out.text("point-label", label, key)
        out.text("point-date", "end of " + _month(month), key)
        out.end("div")
    out.end("div")
    out.end("div")
    out.end("div")
    _sentences(out, card, 1)


def _direction(claim):
    if claim is None:
        return "not covered"
    if claim["direction"] == "flat":
        return "unchanged (" + claim["display"] + ")"
    return claim["direction"] + " " + claim["display"]


def _panic(out, page, card, claims):
    for i, window in enumerate(_WINDOWS):
        out.start("div", {"data-layout": "episode"})
        out.start("div", {"data-layout": "episode-copy"})
        _sentences(out, card, 2 * i, 2 * i + 2)
        out.end("div")
        out.start("div", {"data-layout": "chips"})
        if i == 0:
            out.text("chips-label", "Over the period")
        for series, label, suffix in (("asset", page["instrument"]["label"], ""),
                                       ("tracker", "Tracker", ".tracker")):
            key = window + "." + series
            out.start("div", {"data-layout": "chip"})
            out.text("chip-label", label, key)
            out.text("chip-value", _direction(claims.get("panic." + window + suffix)), key)
            out.end("div")
        out.end("div")
        out.end("div")
    _sentences(out, card, 6)


def _next(out, page, card, claims):
    asset_id = page["instrument"]["id"]
    correlation = claims["next.correlation"]
    lowest = claims["next.rolling_lowest"]
    highest = claims["next.rolling_highest"]
    out.start("div", {"data-layout": "card-lead"})
    out.start("div", {"data-layout": "lead-copy"})
    out.text("figure", correlation["display"], "next.correlation")
    _sentences(out, card, 0, 1)
    out.end("div")
    out.start("div", {"data-layout": "correlation"})
    out.text("scale-label", "Correlation with the tracker")
    out.text("scale-value", correlation["display"], "next.correlation")
    out.size(asset_id, "next.correlation", lambda: (correlation["value"] + 1) / 2)
    out.start("div", {"data-layout": "scale-points"})
    for key, mark, note in (("low", "−1", "always opposite"), ("mid", "0", "no pattern"),
                             ("high", "1", "always in step")):
        out.start("div", {"data-layout": "scale-point"})
        out.text("scale-mark", mark, key)
        out.text("scale-note", note, key)
        out.end("div")
    out.end("div")
    out.text("range", "Range across 36-month stretches: " + lowest["display"] + " to " + highest["display"])
    out.size(asset_id, "next.range-low", lambda: (lowest["value"] + 1) / 2)
    out.size(asset_id, "next.range-high", lambda: (highest["value"] + 1) / 2)
    out.end("div")
    out.end("div")
    _sentences(out, card, 1, 3)
    out.start("div", {"data-layout": "mix"})
    out.text("mix-part", "Tracker 90%", "next.tracker")
    out.size(asset_id, "next.tracker", lambda: 0.9)
    out.text("mix-part", page["instrument"]["label"] + " 10%", "next.asset")
    out.size(asset_id, "next.asset", lambda: 0.1)
    out.end("div")
    _sentences(out, card, 3)


def render_page(page, index):
    """Return an asset page as finished HTML after section 16.6 checks."""
    _check_index(index)
    claims = _check_page(page, index)
    guided = _check_guided(page) if "guided" in page else None
    instrument = page["instrument"]
    identity = instrument["identity"]
    headline = page["headline"]
    out = _Markup()
    _head(out, instrument["label"] + ", in pounds · " + SITE_NAME,
          headline["text"] if headline is not None else _TAGLINE, "../")
    out.start("main", {"data-layout": "asset"})
    out.text("back", "All investments", tag="a", attrs={"href": "../"})
    out.start("div", {"data-layout": "asset-intro"})
    out.start("div", {"data-layout": "identity"})
    kicker = _TYPES[identity["type"]]
    if identity["exchange"]:
        kicker += " · " + identity["exchange"]
    out.text("kicker", kicker)
    out.text("asset-label", instrument["label"], tag="h1")
    out.text("asset-name", identity["name"] + " · " + identity["ticker"])
    out.start("div", {"data-layout": "tags"})
    out.text("tag", "Priced in US dollars" if identity["trading_currency"] == "USD"
             else "Priced in pounds", "priced")
    out.text("tag", "Figures in pounds", "figures")
    out.text("tag", page["data_as_of_text"], "data")
    out.end("div")
    out.end("div")
    out.start("div", {"data-layout": "headline"})
    out.text("section-label", "The headline", "headline")
    if headline is None:
        out.text("no-headline", "No reviewed headline for this data yet. A headline appears "
                 "here only after a person has reviewed it.")
    else:
        out.text("headline", headline["text"], instrument["id"])
        out.start("div", {"data-layout": "chain"})
        for key, label, detail in (
            ("drafted", "Drafted by AI", headline["drafted_by"]),
            ("checked", "Checked by code", _rules_passed()),
            ("reviewed", "Reviewed by a person", _day(headline["reviewed_on"])),
        ):
            out.start("div", {"data-layout": "chain-step"})
            out.text("chain", label, key)
            out.text("chain-detail", detail, key)
            out.end("div")
        out.end("div")
    out.end("div")
    out.end("div")
    out.start("div", {"data-layout": "asset-body"})
    out.start("nav", {"data-layout": "rail"})
    out.text("rail-label", "The questions")
    out.start("div", {"data-layout": "rail-links"})
    for i, card in enumerate(page["cards"], 1):
        out.start("a", {"href": "#" + card["id"]})
        out.text("rail-number", format(i, "02d"), card["id"], tag="span")
        out.text("rail-title", card["title"], card["id"], tag="span")
        out.end("a")
    out.end("div")
    out.start("div", {"data-layout": "benchmark"})
    out.text("compared-label", "Compared with")
    out.text("benchmark-label", page["benchmark"]["label"])
    benchmark = page["benchmark"]["identity"]
    out.text("benchmark-name", benchmark["name"] + " · " + benchmark["ticker"])
    out.end("div")
    out.end("nav")
    out.start("div", {"data-layout": "cards"})
    if guided is not None:
        _guided_controls(out, page["cards"])
    renderers = {"bumpy": _bumpy, "worst": _worst, "panic": _panic, "next": _next}
    for i, card in enumerate(page["cards"], 1):
        card_id = card["id"]
        out.start("section", {"id": card_id})
        out.start("div", {"data-layout": "card-heading"})
        out.text("card-number", format(i, "02d"), card_id)
        if card_id in ("next", "pound"):
            out.start("h2", {"data-qx": "card-title", "data-qx-key": card_id})
            out.start("button", {"type": "button", "data-accordion-toggle": "",
                                 "aria-expanded": "true", "aria-disabled": "true",
                                 "aria-controls": card_id + "-content"})
            out.parts[-1] += html.escape(card["title"], quote=True)
            out.end("button")
            out.end("h2")
        else:
            out.text("card-title", card["title"], card_id, tag="h2")
        out.end("div")
        if card_id in ("next", "pound"):
            out.start("div", {"data-layout": "card-content", "id": card_id + "-content"})
        if card_id in renderers:
            renderers[card_id](out, page, card, claims)
            _maths(out, page, card_id, claims)
        else:
            _sentences(out, card)
        if guided is not None:
            _guided(out, guided[i - 1])
        if card_id in ("next", "pound"):
            out.end("div")
        out.end("section")
    out.end("div")
    out.end("div")
    out.end("main")
    _footer(out, page, page["sources"], identity)
    return out.finish()


def _rules_passed():
    return "{0} of {0} rules passed".format(HEADLINE_RULE_COUNT)


def _merge_sources(pages):
    merged = {}
    for page in pages:
        for source in page["sources"]:
            provider = source["provider"]
            if provider not in merged:
                merged[provider] = {"provider": provider, "url": source["url"], "used_for": []}
            elif source["url"] != merged[provider]["url"]:
                raise SiteError("landing: sources: " + provider + " url differs")
            labels = merged[provider]["used_for"]
            for label in source["used_for"]:
                if label not in labels:
                    labels.append(label)
    return list(merged.values())


def check_reviews(reviews, index, pages):
    """Check the review record and its published approvals in section 16.9 order."""
    if (not isinstance(reviews, dict) or not isinstance(reviews.get("reviews"), list)
            or not reviews["reviews"]):
        raise SiteError("reviews: unreadable")
    records = reviews["reviews"]
    seen = set()
    for number, review in enumerate(records, 1):
        message = "reviews: {}: unreadable".format(number)
        if (not isinstance(review, dict)
                or any(not _nonblank(review.get(key)) for key in ("id", "title", "reviewer"))
                or not isinstance(review.get("reviewed_on"), str)
                or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", review["reviewed_on"])
                or not isinstance(review.get("data_as_of"), str)
                or not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", review["data_as_of"])
                or not isinstance(review.get("assets"), dict)):
            raise SiteError(message)
        try:
            datetime.date.fromisoformat(review["reviewed_on"])
        except ValueError:
            raise SiteError(message) from None
        if review["id"] in seen:
            raise SiteError("reviews: duplicate id " + review["id"])
        seen.add(review["id"])
    if any(newer["data_as_of"] <= older["data_as_of"]
           for newer, older in zip(records, records[1:])):
        raise SiteError("reviews: order")

    asset_ids = {asset["id"] for asset in index["assets"]}
    round_keys = {"round", "verdict", "text", "reason", "control"}
    for review in records:
        prefix = "reviews: " + review["id"] + ": "
        for asset_id, rounds in review["assets"].items():
            if asset_id not in asset_ids:
                raise SiteError(prefix + "unknown asset " + str(asset_id))
            asset_prefix = prefix + asset_id + ": "
            if (not isinstance(rounds, list) or any(
                    not isinstance(item, dict) or set(item) != round_keys
                    for item in rounds)):
                raise SiteError(asset_prefix + "unreadable")
            if any(type(item["round"]) is not int or item["round"] != number
                   for number, item in enumerate(rounds, 1)):
                raise SiteError(asset_prefix + "round numbers")
            for item in rounds:
                round_prefix = asset_prefix + "round {}: ".format(item["round"])
                if item["verdict"] not in ("approved", "rejected", "redrafted"):
                    raise SiteError(round_prefix + "verdict")
                if not _nonblank(item["text"]):
                    raise SiteError(round_prefix + "text")
                if item["verdict"] == "approved":
                    invalid_reason = item["reason"] is not None or item["control"] is not None
                else:
                    invalid_reason = (not _nonblank(item["reason"])
                                      or (item["control"] is not None
                                          and not _nonblank(item["control"])))
                if invalid_reason:
                    raise SiteError(round_prefix + "reason")
            if any(item["verdict"] == "approved" for item in rounds[:-1]):
                raise SiteError(asset_prefix + "approved must be the last round")

    latest = records[0]
    if latest["data_as_of"] != index["data_as_of"]:
        raise SiteError("reviews: latest is not for " + index["data_as_of"])
    prefix = "reviews: " + latest["id"] + ": "
    for asset, page in zip(index["assets"], pages):
        asset_id = asset["id"]
        if asset_id not in latest["assets"]:
            raise SiteError(prefix + "missing " + asset_id)
        rounds = latest["assets"][asset_id]
        approved = bool(rounds) and rounds[-1]["verdict"] == "approved"
        headline = page["headline"]
        asset_prefix = prefix + asset_id + ": "
        if headline is not None and not approved:
            raise SiteError(asset_prefix + "headline not approved")
        if approved and headline is None:
            raise SiteError(asset_prefix + "approved without a headline")
        if approved and rounds[-1]["text"] != headline["text"]:
            raise SiteError(asset_prefix + "approved text differs from the headline")


def _trail_button(out, asset_id, attrs=None):
    attributes = {"type": "button", "aria-haspopup": "dialog", "data-trail": asset_id}
    attributes.update(attrs or {})
    out.start("button", attributes)


def _trail_drawers(out, index, pages, reviews):
    """Write the complete, initially hidden audit history in index order."""
    month = _month(index["data_as_of"])
    verdicts = {"approved": "Approved", "rejected": "Rejected", "redrafted": "Redrafted, not used"}
    out.start("div", {"hidden": None})
    for asset, page in zip(index["assets"], pages):
        key, label, headline = asset["id"], asset["label"], page["headline"]
        out.start("section", {
            "role": "dialog", "aria-modal": "true", "id": "trail-" + key,
            "aria-labelledby": "trail-title-" + key, "hidden": None,
        })
        out.text("trail-label", "Audit trail", key)
        title = ("How " + label + "'s headline was made" if headline is not None
                 else "Why " + label + " has no headline for " + month)
        out.text("trail-title", title, key, tag="h2", attrs={"id": "trail-title-" + key})
        out.text("trail-close", "Close the audit trail", key, tag="button",
                 attrs={"type": "button"}, text_attr="aria-label")
        if headline is not None:
            out.text("trail-status", "Published · data to the end of " + month, key)
            out.text("trail-headline", headline["text"], key)
            out.text("trail-step", "Drafted by " + headline["drafted_by"], key + ".1")
            out.text("trail-step-text", "It saw only figures from " + label
                     + "'s own page and could cite only those. It cited "
                     + _COUNTS[len(headline["claims"]) - 1] + " of them.", key + ".1")
            out.text("trail-step", "Checked by code: " + _rules_passed(), key + ".2")
            for number, rule in enumerate(_TRAIL_RULES, 1):
                out.text("trail-rule", rule, key + ".r{:02d}".format(number))
            out.text("trail-step", "Reviewed by a person · approved "
                     + _day(headline["reviewed_on"]), key + ".3")
            out.text("trail-step-text", "Read against " + label
                     + "'s page. When next month's data arrives, this line comes down "
                     "until a new one is reviewed.", key + ".3")
        else:
            out.text("trail-status", "Not published · data to the end of " + month, key)
            out.text("trail-none", "No draft was approved for this data, so no line is shown "
                     "until one passes review.", key)
        out.text("trail-earlier", "Every draft, including the rejected ones", key, tag="h3")
        out.text("trail-note", "Each passed the code checks of its day. Each verdict is a person's.", key)
        for review in reviews["reviews"]:
            if key not in review["assets"]:
                continue
            review_key = key + "." + review["id"]
            out.text("trail-review", review["title"] + " · reviewed by " + review["reviewer"]
                     + ", " + _day(review["reviewed_on"]) + " · data to the end of "
                     + _month(review["data_as_of"]), review_key)
            for item in review["assets"][key]:
                round_key = review_key + "." + str(item["round"])
                out.text("trail-round", "Round {} · {}".format(
                    item["round"], verdicts[item["verdict"]]), round_key,
                    attrs={"data-verdict": item["verdict"]})
                out.text("trail-draft", item["text"], round_key)
                if item["reason"] is not None:
                    out.text("trail-reason", item["reason"], round_key)
                if item["control"] is not None:
                    out.text("trail-control", "Now: " + item["control"], round_key)
        out.end("section")
    out.end("div")


def render_landing(index, pages, reviews=None):
    """Return the landing page as finished HTML, preserving index order."""
    _check_index(index)
    if (not isinstance(pages, list)
            or any(not isinstance(p, dict) or not isinstance(p.get("instrument"), dict)
                   for p in pages)
            or [p["instrument"].get("id") for p in pages]
            != [a["id"] for a in index["assets"]]):
        raise SiteError("landing: pages do not match the index")
    for page in pages:
        _check_page(page, index)
    sources = _merge_sources(pages)
    if reviews is not None:
        check_reviews(reviews, index, pages)
    assets = index["assets"]
    tagline = (
        "Plain-English explanations of how investments have behaved, in pounds. "
        "Every figure comes from tested code. The one line an AI writes is checked against "
        + str(HEADLINE_RULE_COUNT) + " rules and read by a person before it goes live."
    )
    out = _Markup()
    _head(out, SITE_NAME + ": investments in plain English", tagline, "")
    out.start("main", {"data-layout": "landing"})
    out.start("div", {"data-layout": "landing-intro"})
    out.text("kicker", "A governed AI demo · in pounds")
    out.start("h1", {"data-qx": "hero"})
    out.parts[-1] += html.escape("AI drafts it. Code checks it.", quote=True)
    out.start("span", {"data-layout": "hero-accent"})
    out.parts[-1] += html.escape("A person signs it off.", quote=True)
    out.end("span")
    out.end("h1")
    out.text("tagline", tagline)
    out.start("div", {"data-layout": "search", "hidden": None})
    out.text("search-label", "What am I actually getting into?", tag="label", attrs={"for": "asset-search"})
    out.start("div", {"data-layout": "search-field"})
    out.text("search-hint", "Try " + assets[0]["label"] + " or " + assets[0]["ticker"],
             tag="input", attrs={"id": "asset-search", "type": "search"}, text_attr="placeholder")
    out.end("div")
    out.start("ul")
    for asset in assets:
        key = asset["id"]
        out.start("li", {"hidden": None})
        out.start("a", {"href": key + "/"})
        for field in ("label", "ticker", "name"):
            out.text("result-" + field, asset[field], key, tag="span")
        out.end("a")
        out.end("li")
    out.end("ul")
    out.start("div", {"data-layout": "not-covered", "hidden": None})
    out.text("not-covered-title", "Not covered yet")
    out.text("not-covered-text", "Each investment here is covered in depth: every figure comes from "
             "tested code, and every headline is reviewed by a person.")
    out.end("div")
    out.end("div")
    out.end("div")
    headlines = [(asset, page["headline"]) for asset, page in zip(assets, pages) if page["headline"] is not None]
    if headlines:
        out.start("section", {"data-layout": "headlines"})
        out.text("section-label", "In one line", "headlines")
        for i, (asset, headline) in enumerate(headlines, 1):
            key = asset["id"]
            out.start("article")
            out.start("div", {"data-layout": "slide-heading"})
            out.text("slide-position", "{} / {}".format(i, len(headlines)), key)
            out.text("slide-label", asset["label"], key)
            out.text("slide-ticker", asset["ticker"], key)
            out.end("div")
            out.text("headline", headline["text"], key)
            if reviews is None:
                out.start("div", {"data-layout": "audit"})
            else:
                _trail_button(out, key, {"data-layout": "audit"})
            out.text("audit-drafted", "Drafted by " + headline["drafted_by"], key)
            out.text("audit-checked", "{0} of {0} rules".format(HEADLINE_RULE_COUNT), key)
            out.text("audit-reviewed", "Reviewed " + _day(headline["reviewed_on"]), key)
            if reviews is None:
                out.end("div")
            else:
                out.text("audit-open", "Audit trail", key, tag="span")
                out.end("button")
            out.text("slide-open", "Open " + asset["label"], key, tag="a", attrs={"href": key + "/"})
            out.end("article")
        out.start("div", {"data-layout": "headline-controls", "hidden": None})
        out.start("button", {"type": "button", "data-layout": "headline-toggle"})
        out.text("pause", "Pause the headlines", tag="span")
        out.text("play", "Play the headlines", tag="span", attrs={"hidden": None})
        out.end("button")
        for asset, headline in headlines:
            out.text("segment", "Show the headline for " + asset["label"], asset["id"],
                     tag="button", attrs={"type": "button"}, text_attr="aria-label")
        out.end("div")
        out.end("section")
    out.start("section", {"data-layout": "gates"})
    out.text("gates-title", "How a headline gets published", tag="h2")
    out.start("div", {"data-layout": "gates-grid"})
    for key, title, text in (
        ("01", "Drafted by AI",
         "A model writes one line per investment. It sees only figures from that "
         "investment's own page, and can cite only those."),
        ("02", "Checked by code: " + str(HEADLINE_RULE_COUNT) + " rules",
         "No advice, no forecasts, no rankings, every number traced to the page. "
         "One failure and the line is out."),
        ("03", "Reviewed by a person",
         "In the first round, all 7 drafts passed every code check."),
    ):
        out.start("article", {"data-layout": "gate", "data-gate": key})
        out.start("div", {"data-layout": "gate-heading"})
        out.text("gate-number", key, key)
        out.text("gate-title", title, key, tag="h3")
        out.end("div")
        if key == "03":
            out.start("p", {"data-qx": "gate-text", "data-qx-key": key})
            out.parts[-1] += html.escape(text, quote=True)
            out.start("strong")
            out.parts[-1] += html.escape("A person rejected 6.", quote=True)
            out.end("strong")
            out.parts[-1] += html.escape(
                " Most reasons became new rules. The rest are why a person stays in the loop.",
                quote=True,
            )
            out.end("p")
            if reviews is not None:
                latest_assets = reviews["reviews"][0]["assets"]
                target = next((asset["id"] for asset in assets
                               if any(item["verdict"] == "rejected"
                                      for item in latest_assets[asset["id"]])), assets[0]["id"])
                _trail_button(out, target)
                out.text("gate-open", "See the audit trail", key, tag="span")
                out.end("button")
        else:
            out.text("gate-text", text, key)
        out.end("article")
    out.end("div")
    out.end("section")
    out.start("div", {"data-layout": "tiles"})
    out.text("tiles-label", "Or pick one")
    out.start("div", {"data-layout": "tile-grid"})
    for asset in assets:
        key = asset["id"]
        out.start("a", {"href": key + "/"})
        out.text("tile-ticker", asset["ticker"], key, tag="span")
        out.text("tile-label", asset["label"], key, tag="span")
        out.end("a")
    out.end("div")
    out.end("div")
    out.end("main")
    if reviews is not None:
        _trail_drawers(out, index, pages, reviews)
    _footer(out, index, sources)
    return out.finish()
