"""Offline source and golden-page checks for the site's progressive enhancement."""

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

from golden_support import apply_edits, load_golden
from web.render import render_landing, render_page


_ASSETS = Path(__file__).resolve().parents[1] / "site" / "assets"
_SCRIPT = _ASSETS / "site.js"
_STYLESHEET = _ASSETS / "site.css"
_GOLDEN = load_golden("site_render.json")
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
