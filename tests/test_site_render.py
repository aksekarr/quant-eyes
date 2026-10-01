"""Golden read-back and markup checks for the pure site renderer."""

from copy import deepcopy
from html.parser import HTMLParser
import re
import unittest

from web.render import (
    HEADLINE_RULE_COUNT,
    SITE_NAME,
    SiteError,
    render_landing,
    render_page,
)
from golden_support import apply_edits, generate_golden_tests, load_golden


_GOLDEN = load_golden("site_render.json")
_VOID_TAGS = frozenset(("meta", "link", "input", "br"))
_ALLOWED_TAGS = frozenset(
    "html head meta title link script body header main footer nav section article "
    "div span p a h1 h2 h3 ul ol li dl dt dd figure figcaption details summary "
    "table thead tbody tr th td button label input svg path circle line polyline "
    "rect g strong em small abbr br".split()
)
_SIZE_STYLE = re.compile(r"--qx-size:([0-9]\.[0-9]{4})\Z")


def _normalise_text(text):
    # Section 16.2 names these five whitespace characters, not Unicode whitespace.
    return re.sub(r"[ \t\n\r\f]+", " ", text).strip(" \t\n\r\f")


class _PageReader(HTMLParser):
    """Retain document order, decoded text, attributes and element ancestry."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.stack = []
        self.text_nodes = []
        self.comments = []

    def handle_starttag(self, tag, attrs):
        element = {
            "tag": tag,
            "attributes": attrs,
            "attrs": dict(attrs),
            "ancestors": tuple(self.stack),
            "text": [],
        }
        self.elements.append(element)
        if tag not in _VOID_TAGS:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        # Pair the end tag with the nearest open element of the same name.
        for position in range(len(self.stack) - 1, -1, -1):
            if self.stack[position]["tag"] == tag:
                del self.stack[position:]
                break

    def handle_data(self, data):
        self.text_nodes.append((data, tuple(self.stack)))
        for element in self.stack:
            element["text"].append(data)

    def handle_comment(self, data):
        self.comments.append(data)

    def entries(self):
        entries = []
        for element in self.elements:
            attrs = element["attrs"]
            if "data-qx" not in attrs:
                continue
            if "data-qx-attr" in attrs:
                text = attrs[attrs["data-qx-attr"]]
            else:
                text = "".join(element["text"])
            size = None
            if "style" in attrs:
                size = _SIZE_STYLE.fullmatch(attrs["style"]).group(1)
            entries.append(
                [
                    attrs["data-qx"],
                    attrs.get("data-qx-key", ""),
                    _normalise_text(text),
                    size,
                ]
            )
        return entries


def _ancestor(element, tag):
    return next(
        (item for item in reversed(element["ancestors"]) if item["tag"] == tag),
        None,
    )


class SiteRenderGoldenTests(unittest.TestCase):
    def exercise_case(self, case):
        index = apply_edits(_GOLDEN["index"][case["index"]], case["index_edits"])
        is_landing = case["check"] in ("landing", "landing_error")
        if is_landing:
            pages = [
                apply_edits(
                    _GOLDEN["pages"][name], case["page_edits"].get(name, [])
                )
                for name in case["pages"]
            ]
            inputs = (index, pages)
            render = lambda: render_landing(index, pages)
        else:
            page = apply_edits(_GOLDEN["pages"][case["page"]], case["page_edits"])
            pages = [page]
            inputs = (page, index)
            render = lambda: render_page(page, index)

        original_inputs = deepcopy(inputs)
        outputs = []
        for repeat in range(2):
            with self.subTest(render=repeat + 1):
                if "expected_error" in case:
                    with self.assertRaises(SiteError) as raised:
                        render()
                    self.assertIs(type(raised.exception), SiteError)
                    self.assertEqual(str(raised.exception), case["expected_error"])
                else:
                    rendered = render()
                    self.assertIs(type(rendered), str)
                    reader = _PageReader()
                    reader.feed(rendered)
                    reader.close()
                    self.assert_markup(rendered, reader, index, pages, is_landing)
                    self.assertEqual(reader.entries(), case["expected"])
                    self.assert_structure(reader, index, pages, is_landing)
                    outputs.append(rendered)
                self.assertEqual(inputs, original_inputs)
        if "expected_error" not in case:
            self.assertEqual(len(outputs), 2)
            self.assertEqual(outputs[0], outputs[1])

    def assert_markup(self, rendered, reader, index, pages, is_landing):
        """Check every rule in section 16.7 on each render, including hidden text."""
        self.assertTrue(rendered.startswith('<!doctype html>\n<html lang="en-GB">\n'))
        self.assertTrue(rendered.endswith("</html>\n"))
        self.assertFalse(reader.comments)
        tags = [element["tag"] for element in reader.elements]
        self.assertEqual(tags.count("title"), 1)
        self.assertEqual(tags.count("h1"), 1)
        self.assertEqual(tags.count("script"), 1)
        self.assertNotIn("style", tags)

        prefix = "" if is_landing else "../"
        allowed_links = {"./"} if is_landing else {"../"}
        if is_landing:
            allowed_links.update(asset["id"] + "/" for asset in index["assets"])
        else:
            allowed_links.update("#" + card["id"] for card in pages[0]["cards"])
            allowed_links.update(pages[0]["instrument"]["identity"]["sources"])
        allowed_links.update(
            source["url"] for page in pages for source in page["sources"]
        )

        pairs = set()
        ids = set()
        stylesheet_found = False
        for element in reader.elements:
            tag = element["tag"]
            attrs = element["attrs"]
            self.assertIn(tag, _ALLOWED_TAGS)
            self.assertEqual(len(element["attributes"]), len(attrs))
            self.assertFalse(any(name.startswith("on") for name in attrs))
            # Task 9a adds no class names; the later design task may introduce them.
            self.assertNotIn("class", attrs)
            if "id" in attrs:
                self.assertNotIn(attrs["id"], ids)
                ids.add(attrs["id"])
            if "data-qx" in attrs:
                self.assertFalse(
                    any("data-qx" in parent["attrs"] for parent in element["ancestors"])
                )
                pair = (attrs["data-qx"], attrs.get("data-qx-key", ""))
                self.assertNotIn(pair, pairs)
                pairs.add(pair)
                if attrs["data-qx"] == "card-title":
                    self.assertEqual(tag, "h2")
                if "data-qx-attr" in attrs:
                    self.assertIn(attrs["data-qx-attr"], attrs)
                    self.assertIsInstance(attrs[attrs["data-qx-attr"]], str)
                if attrs["data-qx"] == "size":
                    self.assertIn("data-qx-key", attrs)
                    self.assertIn("style", attrs)
                    self.assertEqual("".join(element["text"]), "")
                    self.assertFalse(
                        any(
                            parent is element
                            for child in reader.elements
                            for parent in child["ancestors"]
                        )
                    )
                if pair == ("figure", "worst.ten_thousand_left"):
                    self.assertEqual(attrs.get("data-qx-from"), "10000")
            if "style" in attrs:
                self.assertEqual(attrs.get("data-qx"), "size")
                self.assertIsNotNone(_SIZE_STYLE.fullmatch(attrs["style"]))
            for name in ("aria-label", "placeholder", "alt", "title"):
                if name in attrs:
                    self.assertIn("data-qx", attrs)
                    self.assertEqual(attrs.get("data-qx-attr"), name)
            if "data-qx-from" in attrs:
                self.assertEqual(attrs.get("data-qx"), "figure")
                self.assertEqual(attrs.get("data-qx-key"), "worst.ten_thousand_left")
                self.assertEqual(attrs["data-qx-from"], "10000")
            if tag == "script":
                self.assertIsNotNone(_ancestor(element, "head"))
                self.assertEqual(set(attrs), {"src", "defer"})
                self.assertEqual(attrs["src"], prefix + "assets/site.js")
                self.assertEqual("".join(element["text"]).strip(), "")
            if tag == "a" and "href" in attrs:
                self.assertIn(attrs["href"], allowed_links)
            if tag == "link":
                self.assertIsNotNone(_ancestor(element, "head"))
                self.assertIn(attrs.get("rel"), {"stylesheet", "preload", "icon"})
                self.assertTrue(attrs.get("href", "").startswith(prefix + "assets/"))
                remainder = attrs["href"][len(prefix + "assets/"):]
                self.assertTrue(remainder)
                self.assertNotIn("..", remainder.split("/"))
                if attrs.get("rel") == "stylesheet":
                    stylesheet_found |= attrs["href"] == prefix + "assets/site.css"
        self.assertTrue(stylesheet_found)
        for text, ancestors in reader.text_nodes:
            if _normalise_text(text) and any(item["tag"] == "body" for item in ancestors):
                self.assertTrue(any("data-qx" in item["attrs"] for item in ancestors))

    def assert_structure(self, reader, index, pages, is_landing):
        """Keep the specified semantics and initial hidden states intact."""
        entries = {
            (item["attrs"]["data-qx"], item["attrs"].get("data-qx-key", "")): item
            for item in reader.elements
            if "data-qx" in item["attrs"]
        }
        heading = entries[("hero" if is_landing else "asset-label", "")]
        self.assertEqual(heading["tag"], "h1")
        self.assertIsNotNone(_ancestor(entries[("title", "")], "head"))
        for role, name, value in (
            ("description", "name", "description"),
            ("og-title", "property", "og:title"),
            ("og-description", "property", "og:description"),
        ):
            item = entries[(role, "")]
            self.assertEqual(item["tag"], "meta")
            self.assertIsNotNone(_ancestor(item, "head"))
            self.assertEqual(item["attrs"].get(name), value)
            self.assertEqual(item["attrs"].get("data-qx-attr"), "content")
        head_meta = [
            item["attrs"]
            for item in reader.elements
            if item["tag"] == "meta" and _ancestor(item, "head") is not None
        ]
        self.assertEqual(
            head_meta[:2],
            [
                {"charset": "utf-8"},
                {"name": "viewport", "content": "width=device-width, initial-scale=1"},
            ],
        )
        self.assertIn({"property": "og:type", "content": "website"}, head_meta)
        self.assert_link(entries[("site-name", "")], "./" if is_landing else "../")
        for page in pages:
            for source in page["sources"]:
                self.assert_link(entries[("source", source["provider"])], source["url"])
        if is_landing:
            search = entries[("search-hint", "")]
            self.assertEqual(search["tag"], "input")
            self.assertEqual(search["attrs"].get("type"), "search")
            label = entries[("search-label", "")]
            self.assertEqual(label["tag"], "label")
            self.assertIn("id", search["attrs"])
            self.assertEqual(label["attrs"].get("for"), search["attrs"]["id"])
            self.assertNotIn(("search-count", ""), entries)
            for role in ("search-label", "search-hint"):
                self.assertTrue(
                    any(
                        "hidden" in item["attrs"]
                        for item in entries[(role, "")]["ancestors"]
                    )
                )
            for asset in index["assets"]:
                for role in ("result-label", "result-ticker", "result-name"):
                    item = entries[(role, asset["id"])]
                    self.assert_link(item, asset["id"] + "/")
                    result = _ancestor(item, "li")
                    self.assertIsNotNone(result)
                    self.assertIn("hidden", result["attrs"])
                for role in ("tile-ticker", "tile-label"):
                    self.assert_link(entries[(role, asset["id"])], asset["id"] + "/")
            for role in ("not-covered-title", "not-covered-text"):
                self.assertTrue(
                    any(
                        "hidden" in item["attrs"]
                        for item in entries[(role, "")]["ancestors"]
                    )
                )
            if any(page["headline"] is not None for page in pages):
                for role in ("pause", "play"):
                    item = entries[(role, "")]
                    button = item if item["tag"] == "button" else _ancestor(item, "button")
                    self.assertIsNotNone(button)
                    self.assertTrue(
                        any("hidden" in parent["attrs"] for parent in button["ancestors"])
                    )
                self.assertIn("hidden", entries[("play", "")]["attrs"])
                for page in pages:
                    if page["headline"] is None:
                        continue
                    asset_id = page["instrument"]["id"]
                    segment = entries[("segment", asset_id)]
                    self.assertEqual(segment["tag"], "button")
                    self.assertEqual("".join(segment["text"]), "")
                    self.assertTrue(
                        any("hidden" in parent["attrs"] for parent in segment["ancestors"])
                    )
                    self.assert_link(entries[("slide-open", asset_id)], asset_id + "/")
            return

        self.assert_link(entries[("back", "")], "../")
        for number, url in enumerate(pages[0]["instrument"]["identity"]["sources"], 1):
            self.assert_link(entries[("identity-source", str(number))], url)
        self.assertIsNotNone(_ancestor(entries[("rail-label", "")], "nav"))
        for card in pages[0]["cards"]:
            card_id = card["id"]
            for role in ("rail-number", "rail-title"):
                item = entries[(role, card_id)]
                self.assertIsNotNone(_ancestor(item, "nav"))
                self.assert_link(item, "#" + card_id)
            section = _ancestor(entries[("card-title", card_id)], "section")
            self.assertIsNotNone(section)
            self.assertEqual(section["attrs"].get("id"), card_id)
            if card_id not in ("bumpy", "worst", "panic", "next"):
                continue
            show = entries[("maths-show", card_id)]
            hide = entries[("maths-hide", card_id)]
            summary = _ancestor(show, "summary")
            self.assertIsNotNone(summary)
            self.assertIs(_ancestor(hide, "summary"), summary)
            self.assertIsNotNone(_ancestor(summary, "details"))
            self.assertIn("hidden", hide["attrs"])

    def assert_link(self, element, href):
        link = element if element["tag"] == "a" else _ancestor(element, "a")
        self.assertIsNotNone(link)
        self.assertEqual(link["attrs"].get("href"), href)

    def test_site_constants(self):
        self.assertEqual(SITE_NAME, _GOLDEN["interface"]["constants"]["SITE_NAME"])
        self.assertEqual(
            HEADLINE_RULE_COUNT,
            _GOLDEN["interface"]["constants"]["HEADLINE_RULE_COUNT"],
        )

    def test_headline_rule_count_matches_golden_rules(self):
        rules = {
            rule
            for case in load_golden("headline.json")["cases"]
            for rule in case.get("expected_rules", [])
        }
        self.assertEqual(HEADLINE_RULE_COUNT, len(rules))

    def test_malformed_nested_page_items_raise_site_errors(self):
        # Messages are copied from section 16.6 steps 5 and 6.
        for path, message in (
            (["sources", 0], "usa: sources: provider"),
            (["cards", 0], "usa: cards: order"),
            (["cards", 0, "sentences", 0], "usa: cards: bumpy"),
        ):
            with self.subTest(path=path):
                self.exercise_case({
                    "check": "page_error",
                    "index": "IDX3",
                    "index_edits": [],
                    "page": "P_USA",
                    "page_edits": [{"path": path, "set": None}],
                    "expected_error": message,
                })

    def test_unreadable_landing_page_ids_raise_site_errors(self):
        # Section 16.6 requires the page ids to match the index before page checks.
        for path in ([1], [1, "instrument"]):
            with self.subTest(path=path):
                index = apply_edits(_GOLDEN["index"]["IDX3"], [])
                pages = apply_edits(
                    [_GOLDEN["pages"][name] for name in ("P_USA", "P_GBF", "P_CRY")],
                    [{"path": path, "set": None}],
                )
                original_inputs = deepcopy((index, pages))
                for repeat in range(2):
                    with self.subTest(render=repeat + 1):
                        with self.assertRaises(SiteError) as raised:
                            render_landing(index, pages)
                        self.assertIs(type(raised.exception), SiteError)
                        self.assertEqual(
                            str(raised.exception),
                            "landing: pages do not match the index",
                        )
                        self.assertEqual((index, pages), original_inputs)


generate_golden_tests(
    SiteRenderGoldenTests,
    _GOLDEN["cases"],
    {"page", "landing", "page_error", "landing_error"},
)


if __name__ == "__main__":
    unittest.main()
