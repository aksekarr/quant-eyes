"""Fixed guided explanations using page claims, for methodology section 18."""

from words.cards import WordsError, month_name


_EVERYDAY = {
    "bumpy": (
        "Two roads to the same town, one flat, one hilly. Volatility measures "
        "the hills, not where the road ends up."
    ),
    "worst": (
        "The deepest dip on a walk, measured from the highest point you'd "
        "reached so far."
    ),
    "panic": "Three storms, and how it came out of each one, start to finish.",
    "next": (
        "Two friends' moods: near 1, when one is up the other usually is too; "
        "near 0, one's mood tells you nothing about the other's."
    ),
    "pound": (
        "Buying something abroad: the price can change, and so can the exchange "
        "rate. You feel both."
    ),
    "limits": (
        "A rear-view mirror: it shows clearly where you've been, not what's "
        "round the next bend."
    ),
}


def _panel(title, text):
    return {"title": title, "text": text}


def _has(claims, *names):
    return all(name in claims for name in names)


def _moved(claim):
    if claim["direction"] == "flat":
        return "unchanged ({})".format(claim["display"])
    return "{} {}".format(claim["direction"], claim["display"])


def _fx(claim):
    if claim["direction"] == "flat":
        return "was unchanged ({})".format(claim["display"])
    verb = {"up": "rose", "down": "fell"}[claim["direction"]]
    return "{} {}".format(verb, claim["display"])


def _bumpy(claims, facts):
    panels = []
    if "bumpy.volatility" in claims:
        own = claims["bumpy.volatility"]
        panels.append(_panel(
            "What goes in",
            "One number for each month: how much a holding changed in pounds "
            "from one month-end to the next, with any income added back, from "
            "the end of {} to the end of {}.".format(
                month_name(own["period_start"]), month_name(own["period_end"])
            ),
        ))
    panels.extend([
        _panel(
            "How spread out they were",
            "Volatility measures how far those monthly changes typically sat "
            "from their average, rises and falls alike. Bigger swings either "
            "way give a higher figure.",
        ),
        _panel(
            'Why "a year"',
            "The monthly spread is scaled to a yearly figure by multiplying "
            "it by the square root of 12. It is the usual convention, so "
            "investments can be compared on the same footing.",
        ),
    ])
    asset_id = (
        "bumpy.volatility_common" if "bumpy.volatility_common" in claims
        else "bumpy.volatility"
    )
    if _has(claims, asset_id, "bumpy.tracker_volatility"):
        tracker = claims["bumpy.tracker_volatility"]
        panels.append(_panel(
            "Next to the tracker",
            "Over the months both cover, from the end of {} to the end of {}: "
            "{}, against {} for the developed-world tracker.".format(
                month_name(tracker["period_start"]),
                month_name(tracker["period_end"]),
                claims[asset_id]["display"], tracker["display"],
            ),
        ))
    panels.append(_panel(
        "What it can't tell you",
        "It treats a rise and a fall of the same size alike, and it says "
        "nothing about next month. A calm stretch can end suddenly.",
    ))
    return panels


def _worst(claims, facts):
    panels = []
    if _has(claims, "worst.months_to_low", "worst.fall"):
        fall = claims["worst.fall"]
        panels.append(_panel(
            "From high to low",
            "{}, from the end of {} to the end of {}.".format(
                claims["worst.months_to_low"]["display"],
                month_name(fall["period_start"]), month_name(fall["period_end"]),
            ),
        ))
    if _has(claims, "worst.ten_thousand_left", "worst.ten_thousand_lost"):
        panels.append(_panel(
            "In money",
            "£10,000 invested at that high would have been worth {} at the "
            "low, {} less. That applies only to money put in at the high.".format(
                claims["worst.ten_thousand_left"]["display"],
                claims["worst.ten_thousand_lost"]["display"],
            ),
        ))
    if _has(claims, "worst.months_to_recover", "worst.months_underwater"):
        recovery = claims["worst.months_to_recover"]
        panels.append(_panel(
            "Getting back",
            "It was back at that high by the end of {}: {} after the low, {} "
            "after the high.".format(
                month_name(recovery["period_end"]), recovery["display"],
                claims["worst.months_underwater"]["display"],
            ),
        ))
    elif _has(claims, "worst.below_high_at_end", "worst.months_underwater"):
        below = claims["worst.below_high_at_end"]
        panels.append(_panel(
            "Still below the high",
            "It had not recovered by the end of {}: still {} below its high, "
            "{} after it.".format(
                month_name(below["period_end"]), below["display"],
                claims["worst.months_underwater"]["display"],
            ),
        ))
    panels.append(_panel(
        "What month-ends hide",
        "A fall that recovered within the same month doesn't show, so the "
        "worst moment may have been deeper.",
    ))
    return panels


def _panic(claims, facts):
    windows = (
        ("gfc", "global financial crisis"),
        ("covid", "Covid crash"),
        ("rate_shock", "2022 rate shock"),
    )
    movements = [
        _moved(claims["panic." + name]) if "panic." + name in claims
        else "not covered"
        for name, title in windows
    ]
    panels = [_panel(
        "Three named periods",
        "Global financial crisis: {}. Covid crash: {}. 2022 rate shock: {}. "
        "In pounds, from the start to the end of each period.".format(*movements),
    )]
    if "pound.local" in claims:
        for name, title in windows:
            prefix = "pound." + name + "."
            if _has(claims, prefix + "local", prefix + "currency", prefix + "gbp"):
                panels.append(_panel(
                    "Why the dollar matters here",
                    "Over the {} it was {} in dollars, and the dollar {} "
                    "against the pound, so in pounds it was {}. Step 5 shows "
                    "how the two parts combine.".format(
                        title, _moved(claims[prefix + "local"]),
                        _fx(claims[prefix + "currency"]),
                        _moved(claims[prefix + "gbp"]),
                    ),
                ))
                break
    elif facts["priced_in_pounds_holds_dollars"]:
        panels.append(_panel(
            "Priced in pounds, holding dollars",
            "It is priced in pounds, but what it holds is priced in dollars, "
            "so the exchange rate is already inside these figures.",
        ))
    else:
        panels.append(_panel(
            "Priced in pounds",
            "It is priced in pounds, so these figures have no separate "
            "exchange-rate part.",
        ))
    panels.append(_panel(
        "What start-to-end hides",
        "Prices may have fallen further in between and partly recovered "
        "before the period ended.",
    ))
    return panels


def _next(claims, facts):
    panels = [_panel(
        "What the number means",
        "1 would mean always moving in step, 0 no pattern, and −1 always "
        "opposite. It measures how consistently the monthly moves lined up, "
        "not how big they were.",
    )]
    if _has(claims, "next.rolling_lowest", "next.rolling_highest"):
        low, high = claims["next.rolling_lowest"], claims["next.rolling_highest"]
        panels.append(_panel(
            "It moves around",
            "Over each 36-month stretch it ranged from {} (the 36 months to "
            "the end of {}) to {} (to the end of {}).".format(
                low["display"], month_name(low["period_end"]),
                high["display"], month_name(high["period_end"]),
            ),
        ))
    if _has(
        claims, "next.mix_annualised", "next.tracker_annualised",
        "next.mix_volatility", "next.tracker_volatility",
    ):
        panels.append(_panel(
            "A 90/10 illustration",
            "90% in the tracker and 10% in this investment, reset every "
            "December: {} a year against {} for the tracker alone, with "
            "volatility of {} against {}. An illustration, not a "
            "recommendation, before fees, trading costs and tax.".format(
                claims["next.mix_annualised"]["display"],
                claims["next.tracker_annualised"]["display"],
                claims["next.mix_volatility"]["display"],
                claims["next.tracker_volatility"]["display"],
            ),
        ))
    panels.append(_panel(
        "Not protection",
        "A low figure does not mean it protects a portfolio: correlation says "
        "nothing about how big the moves were.",
    ))
    if facts["held_by_tracker"]:
        panels.append(_panel(
            "You may already hold it",
            "The tracker already holds these shares, so the 10% adds to a "
            "holding it already has.",
        ))
    return panels


def _pound(claims, facts):
    if "pound.local" in claims:
        panels = [_panel(
            "Two parts",
            "What it did in dollars, and what the dollar did against the "
            "pound. A UK holder gets both.",
        )]
        if _has(claims, "pound.local", "pound.currency", "pound.gbp"):
            panels.append(_panel(
                "How they combine",
                "Over the whole period: {} in dollars, the dollar {} against "
                "the pound, so {} in pounds. The two parts multiply rather "
                "than add, so they never simply add up.".format(
                    _moved(claims["pound.local"]), _fx(claims["pound.currency"]),
                    _moved(claims["pound.gbp"]),
                ),
            ))
        panels.append(_panel(
            "It cuts both ways",
            "When the pound rises against the dollar, a dollar holding loses "
            "some of its gain for a UK holder.",
        ))
        return panels
    if facts["priced_in_pounds_holds_dollars"]:
        return [
            _panel(
                "Hidden in the price",
                "It is priced in pounds, but what it holds is priced in "
                "dollars, so when the dollar moves against the pound, its "
                "price in pounds moves too.",
            ),
            _panel(
                "Why it isn't split out",
                "With only a price in pounds, the part that came from the "
                "exchange rate can't be separated out.",
            ),
        ]
    return [_panel(
        "Nothing to split",
        "It is priced in pounds, so a UK holder's figures have no separate "
        "exchange-rate part.",
    )]


def _limits(claims, facts):
    return [
        _panel(
            "The basis",
            "Past results in pounds, measured at month-ends, before platform "
            "fees, trading costs and tax.",
        ),
        _panel(
            "Not a forecast",
            "Past behaviour does not predict future results. Nothing here "
            "says what to do.",
        ),
    ]


_PANELS = {
    "bumpy": _bumpy,
    "worst": _worst,
    "panic": _panic,
    "next": _next,
    "pound": _pound,
    "limits": _limits,
}


def build_guided(page, facts):
    """Return new guided steps in card order without changing the built page."""
    claims = {claim["id"]: claim for claim in page["claims"]}
    steps = []
    for card in page["cards"]:
        card_id = card["id"]
        if card_id not in _PANELS:
            raise WordsError("guided: unknown card {}".format(card_id))
        everyday = _EVERYDAY[card_id]
        if (card_id == "pound" and "pound.local" not in claims
                and not facts["priced_in_pounds_holds_dollars"]):
            everyday = (
                "Shopping at home: there is no exchange rate between you "
                "and the price."
            )
        steps.append({
            "card": card_id,
            "everyday": everyday,
            "more": _PANELS[card_id](claims, facts),
        })
    return {"steps": steps}
