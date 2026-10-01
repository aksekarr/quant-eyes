"""Task 10b: the product name, the logo in the header and the favicon (METHODOLOGY 16.1, 16.3; SITE-DESIGN "Header logo").

Written by Claude from the spec, before the code. Do not edit."""
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

from golden_support import apply_edits, load_golden
import web.render
from web.render import render_landing, render_page

_ROOT = Path(__file__).resolve().parents[1]
_ASSETS = _ROOT / "site" / "assets"
_GOLDEN = load_golden("site_render.json")
_BRAND = {
    "favicon.svg": "dc1d2ed64909e4e23cf29bc7bafdbf3c1e59b1bdac6744e63a8d59b26a7ac853",
    "logo.svg": "be9bc0e2da6d2467c1d0c279c93e69dd7780084ab9e4f8ce38b0c3d7b0dedb8c",
    "mark.svg": "c1a4fd432242df0dc0ba577567ae2c46d99b1a7b9daab75f43f4a1e4e42a016a",
}


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.in_head = False

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.in_head = True
        if tag == "link":
            self.links.append((self.in_head, dict(attrs)))

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False


def _rendered():
    out = []
    for case in _GOLDEN["cases"]:
        if "expected_error" in case:
            continue
        index = apply_edits(_GOLDEN["index"][case["index"]], case["index_edits"])
        if case["check"] == "landing":
            pages = [apply_edits(_GOLDEN["pages"][name], case["page_edits"].get(name, []))
                     for name in case["pages"]]
            out.append((case["id"], "", render_landing(index, pages)))
        else:
            page = apply_edits(_GOLDEN["pages"][case["page"]], case["page_edits"])
            out.append((case["id"], "../", render_page(page, index)))
    return out


def _rules(css, selector):
    """Bodies of every rule whose selector list contains exactly `selector`."""
    bodies = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selectors = [part.strip() for part in match.group(1).split(",")]
        if selector in selectors:
            bodies.append(match.group(2))
    return bodies


class BrandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (_ASSETS / "site.css").read_text(encoding="utf-8")
        cls.pages = _rendered()

    def test_site_name(self):
        self.assertEqual(web.render.SITE_NAME, "Quant Eyes")

    def test_brand_files_are_the_approved_ones(self):
        for name, digest in _BRAND.items():
            with self.subTest(name=name):
                data = (_ASSETS / "brand" / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
        self.assertEqual(sorted(p.name for p in (_ASSETS / "brand").iterdir()
                                if not p.name.startswith(".")), sorted(_BRAND))

    def test_every_page_links_the_favicon_once_in_the_head(self):
        self.assertTrue(self.pages)
        for case_id, prefix, html in self.pages:
            with self.subTest(case=case_id):
                reader = _Links()
                reader.feed(html)
                reader.close()
                icons = [(in_head, attrs) for in_head, attrs in reader.links
                         if "icon" in attrs.get("rel", "").lower().split()]
                self.assertEqual(icons, [(True, {"rel": "icon", "type": "image/svg+xml",
                                                 "href": prefix + "assets/brand/favicon.svg"})])

    def test_site_name_is_drawn_with_the_logo(self):
        bodies = _rules(self.css, '[data-qx="site-name"]')
        self.assertTrue(any(re.search(r'url\(\s*"brand/logo\.svg"\s*\)', body) for body in bodies),
                        "a [data-qx=\"site-name\"] rule must use url(\"brand/logo.svg\")")

    def test_old_mark_and_tile_are_gone(self):
        self.assertFalse("icons/mark.svg" in self.css, "site.css still uses icons/mark.svg")
        self.assertNotRegex(self.css, r'\[data-qx="site-name"\]::?(before|after)')
        self.assertFalse((_ASSETS / "icons" / "mark.svg").exists())

    def test_site_name_text_stays_available_to_screen_readers(self):
        css = re.sub(r"\s+", "", self.css.lower())
        for match in re.finditer(r'([^{}]*\[data-qx="site-name"\][^{}]*)\{([^{}]*)\}', css):
            body = match.group(2)
            with self.subTest(selector=match.group(1)):
                for banned in ("display:none", "visibility:hidden", "font-size:0", "content:"):
                    self.assertNotIn(banned, body)


if __name__ == "__main__":
    unittest.main()
