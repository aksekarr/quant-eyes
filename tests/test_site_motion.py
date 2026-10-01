"""Offline source and golden-page checks for the site's progressive enhancement."""

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

from golden_support import apply_edits, load_golden
from test_site_render import _PageReader
from web.render import render_landing, render_page
from words.guided import build_guided


_ASSETS = Path(__file__).resolve().parents[1] / "site" / "assets"
_SCRIPT = _ASSETS / "site.js"
_STYLESHEET = _ASSETS / "site.css"
_GOLDEN = load_golden("site_render.json")
_GUIDED_GOLDEN = load_golden("guided.json")
_BANNED_SCRIPT_PATTERNS = {
    "fetch": r"\bfetch\b",
    "XMLHttpRequest": r"\bXMLHttpRequest\b",
    "WebSocket": r"\bWebSocket\b",
    "EventSource": r"\bEventSource\b",
    "import(": r"\bimport\s*\(",
    "navigator.sendBeacon": r"\bnavigator\s*\.\s*sendBeacon\b",
    "eval": r"\beval\b",
    "new Function": r"\bnew\s+Function\b",
    "document.write": r"\bdocument\s*\.\s*write\b",
    "innerHTML": r"\binnerHTML\b",
    "outerHTML": r"\bouterHTML\b",
    "insertAdjacentHTML": r"\binsertAdjacentHTML\b",
    "setInterval": r"\bsetInterval\b",
    "localStorage": r"\blocalStorage\b",
    "sessionStorage": r"\bsessionStorage\b",
}


class _ScriptReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self.in_head = False
        self.current_script = None

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.in_head = True
        elif tag == "script":
            self.current_script = {
                "attrs": attrs,
                "in_head": self.in_head,
                "text": "",
            }
            self.scripts.append(self.current_script)

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        elif tag == "script":
            self.current_script = None

    def handle_data(self, data):
        if self.current_script is not None:
            self.current_script["text"] += data


class SiteMotionTests(unittest.TestCase):
    def test_script_exists_and_has_no_banned_names(self):
        self.assertTrue(_SCRIPT.is_file())
        script = _SCRIPT.read_text(encoding="utf-8")
        self.assertTrue(script.strip())
        for name, pattern in _BANNED_SCRIPT_PATTERNS.items():
            with self.subTest(name=name):
                self.assertNotRegex(script, pattern)

    def test_script_text_writes_are_only_the_silent_count_overlay(self):
        script = _SCRIPT.read_text(encoding="utf-8")
        writes = re.findall(
            r"\b([A-Za-z_$][\w$]*)\s*\.\s*(textContent|innerText|nodeValue)"
            r"\s*(?:[+*/-]?=(?!=)|\+\+|--)",
            script,
        )
        self.assertEqual(writes, [("digits", "textContent")])
        self.assertRegex(script, r'digits\.setAttribute\("aria-hidden", "true"\)')
        self.assertNotRegex(script, r"\b(?:createTextNode|insertAdjacentText)\s*\(")
        self.assertNotRegex(
            script,
            r'''\[\s*["'](?:textContent|innerText|nodeValue)["']\s*\]\s*[+*/-]?=(?!=)''',
        )

    def test_script_does_not_write_accessible_copy(self):
        script = _SCRIPT.read_text(encoding="utf-8")
        self.assertNotRegex(
            script,
            r'''\bsetAttribute\s*\(\s*["'](?:aria-label|placeholder|alt|title)["']''',
        )
        self.assertNotRegex(
            script,
            r"\.\s*(?:ariaLabel|placeholder|alt|title)\s*[+*/-]?=(?!=)",
        )

    def test_guided_controls_are_hidden_buttons_before_the_cards(self):
        for case in _GUIDED_GOLDEN["cases"]:
            if case["check"] != "render_page" or "expected_error" in case:
                continue
            with self.subTest(case=case["id"]):
                page = apply_edits(_GUIDED_GOLDEN["fixture_pages"][case["fixture"]], [])
                page["guided"] = build_guided(page, case["facts"])
                reader = _PageReader()
                reader.feed(render_page(page, _GUIDED_GOLDEN["index"]))
                reader.close()
                controls = [element for element in reader.elements
                            if element["attrs"].get("data-layout") == "guided-controls"]
                self.assertEqual(len(controls), 1)
                nav = controls[0]
                self.assertEqual(nav["tag"], "nav")
                self.assertIn("hidden", nav["attrs"])
                parent = nav["ancestors"][-1]
                siblings = [element for element in reader.elements
                            if element["ancestors"] and element["ancestors"][-1] is parent]
                self.assertEqual(siblings.pop(0)["attrs"].get("data-layout"), "guided-hint")
                self.assertIs(siblings[0], nav)
                self.assertEqual(siblings[1]["tag"], "section")
                self.assertEqual(siblings[1]["attrs"]["id"], page["cards"][0]["id"])
                buttons = [element for element in reader.elements
                           if element["tag"] == "button"
                           and any(ancestor is nav for ancestor in element["ancestors"])]
                expected_roles = ["mode-guided", "mode-full", "step-back"]
                expected_roles += ["step-node"] * len(page["cards"]) + ["step-next"]
                self.assertEqual([button["attrs"].get("data-qx") for button in buttons],
                                 expected_roles)
                for button in buttons:
                    self.assertEqual(button["attrs"].get("type"), "button")
                self.assertEqual(buttons[0]["attrs"].get("aria-pressed"), "false")
                self.assertEqual(buttons[1]["attrs"].get("aria-pressed"), "true")
                for card, node in zip(page["cards"], buttons[3:-1]):
                    self.assertEqual(node["attrs"].get("data-qx-key"), card["id"])
                    self.assertEqual(node["attrs"].get("data-step"), card["id"])
                    self.assertEqual(node["attrs"].get("data-qx-attr"), "aria-label")
                    self.assertEqual("".join(node["text"]).strip(), "")

    def test_stylesheet_animations_have_only_one_iteration(self):
        css = _STYLESHEET.read_text(encoding="utf-8")
        self.assertNotIn("infinite", css.lower())
        counts = re.findall(
            r"(?:^|[;{])\s*(?:-webkit-)?animation-iteration-count\s*:\s*([^;}]+)",
            css,
            re.IGNORECASE,
        )
        for declaration in counts:
            with self.subTest(declaration=declaration):
                # A comma list gives one iteration count for each animation.
                values = re.sub(r"\s*!important\s*$", "", declaration,
                                flags=re.IGNORECASE).split(",")
                self.assertTrue(values)
                for value in values:
                    self.assertEqual(value.strip(), "1")

    def test_stylesheet_has_a_reduced_motion_block(self):
        css = _STYLESHEET.read_text(encoding="utf-8")
        self.assertRegex(
            css,
            r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{",
        )

    def test_golden_pages_have_only_the_deferred_local_script(self):
        rendered_kinds = set()
        for case in _GOLDEN["cases"]:
            if "expected_error" in case:
                continue
            with self.subTest(case=case["id"]):
                index = apply_edits(_GOLDEN["index"][case["index"]], case["index_edits"])
                if case["check"] == "landing":
                    pages = [apply_edits(_GOLDEN["pages"][name],
                                         case["page_edits"].get(name, []))
                             for name in case["pages"]]
                    rendered = render_landing(index, pages)
                    expected = "assets/site.js"
                else:
                    self.assertEqual(case["check"], "page")
                    page = apply_edits(_GOLDEN["pages"][case["page"]], case["page_edits"])
                    rendered = render_page(page, index)
                    expected = "../assets/site.js"
                reader = _ScriptReader()
                reader.feed(rendered)
                reader.close()
                self.assertNotIn('data-layout="guided-controls"', rendered)
                self.assertEqual(len(reader.scripts), 1)
                script = reader.scripts[0]
                self.assertTrue(script["in_head"])
                self.assertEqual(len(script["attrs"]), 2)
                attributes = dict(script["attrs"])
                self.assertEqual(set(attributes), {"src", "defer"})
                self.assertEqual(attributes["src"], expected)
                self.assertIn(attributes["defer"], (None, ""))
                self.assertEqual(script["text"].strip(), "")
                rendered_kinds.add(case["check"])
        self.assertEqual(rendered_kinds, {"page", "landing"})


if __name__ == "__main__":
    unittest.main()
