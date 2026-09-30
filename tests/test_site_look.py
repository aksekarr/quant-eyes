"""Offline checks for the static stylesheet and its golden page links."""

import colorsys
from html.parser import HTMLParser
import math
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

from golden_support import apply_edits, load_golden
from web.render import render_landing, render_page


_ASSETS = Path(__file__).resolve().parents[1] / "site" / "assets"
_STYLESHEET = _ASSETS / "site.css"
_GOLDEN = load_golden("site_render.json")
_URL = re.compile(
    r"\burl\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s'\"()]+))\s*\)",
    re.IGNORECASE,
)
_COLOUR = re.compile(
    r"\#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{4}|[0-9a-f]{3})(?![0-9a-f])"
    r"|\b(?:rgb|hsl)a?\([^)]*\)",
    re.IGNORECASE,
)


def _urls(css):
    return [next(value for value in match.groups() if value is not None)
            for match in _URL.finditer(css)]


def _colour_hsl(colour):
    """Read CSS hex and numeric RGB/HSL forms; alpha does not change hue."""
    if colour.startswith("#"):
        digits = colour[1:]
        if len(digits) in (3, 4):
            digits = "".join(digit * 2 for digit in digits)
        rgb = [int(digits[start:start + 2], 16) / 255.0
               for start in (0, 2, 4)]
    else:
        name, values = colour.lower().split("(", 1)
        # Both comma notation and modern space/slash notation are valid CSS.
        channels = re.split(r"[\s,]+", values[:-1].split("/", 1)[0].strip())
        if len(channels) not in (3, 4):
            raise ValueError("Expected three colour channels: " + colour)
        if name.startswith("rgb"):
            rgb = [float(channel[:-1]) / 100.0 if channel.endswith("%")
                   else float(channel) / 255.0 for channel in channels[:3]]
            rgb = [min(1.0, max(0.0, channel)) for channel in rgb]
        else:
            hue = channels[0]
            for unit, multiplier in (("grad", 0.9), ("turn", 360.0),
                                     ("rad", 180.0 / math.pi), ("deg", 1.0)):
                if hue.endswith(unit):
                    hue = float(hue[:-len(unit)]) * multiplier
                    break
            else:
                hue = float(hue)
            if not all(channel.endswith("%") for channel in channels[1:3]):
                raise ValueError("Expected HSL percentages: " + colour)
            saturation, lightness = [min(1.0, max(0.0, float(channel[:-1]) / 100.0))
                                     for channel in channels[1:3]]
            rgb = colorsys.hls_to_rgb((hue % 360.0) / 360.0, lightness, saturation)
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)
    return hue * 360.0, saturation * 100.0, lightness * 100.0


class _StylesheetReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "link" and "stylesheet" in attributes.get("rel", "").lower().split():
            self.stylesheets.append(attributes.get("href"))


class SiteLookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = _STYLESHEET.read_text(encoding="utf-8")

    def test_stylesheet_exists_and_has_no_forbidden_tokens(self):
        self.assertTrue(_STYLESHEET.is_file())
        self.assertTrue(self.css.strip())
        lowered = self.css.lower()
        for token in ("http:", "https:", "@import", "@keyframes", "animation",
                      "infinite", "javascript:", "expression("):
            with self.subTest(token=token):
                self.assertNotIn(token, lowered)
        self.assertNotRegex(lowered, r"url\(\s*['\"]?//")

    def test_every_url_is_a_relative_existing_asset(self):
        urls = _urls(self.css)
        self.assertTrue(urls)
        self.assertEqual(len(urls), len(re.findall(r"\burl\(", self.css, re.IGNORECASE)))
        for url in urls:
            with self.subTest(url=url):
                parts = urlsplit(url)
                self.assertFalse(parts.scheme or parts.netloc)
                self.assertFalse(parts.query or parts.fragment)
                self.assertTrue(parts.path)
                self.assertFalse(parts.path.startswith("/"))
                self.assertNotIn("\\", parts.path)
                path = (_ASSETS / parts.path).resolve()
                self.assertIn(_ASSETS.resolve(), path.parents)
                self.assertTrue(path.is_file(), "Missing CSS asset: " + url)

    def test_every_font_has_its_own_face_and_approved_family(self):
        faces = re.findall(r"@font-face\s*\{([^{}]*)\}", self.css, re.IGNORECASE)
        families = {
            "sora": "Sora",
            "atkinson-hyperlegible-next": "Atkinson Hyperlegible Next",
            "ibm-plex-mono": "IBM Plex Mono",
        }
        font_files = sorted((_ASSETS / "fonts").glob("*.woff2"))
        self.assertTrue(font_files)
        self.assertEqual(len(faces), len(font_files))
        found_families = set()
        for font_file in font_files:
            with self.subTest(font=font_file.name):
                font_url = "fonts/" + font_file.name
                matching = [face for face in faces if font_url in _urls(face)]
                self.assertEqual(len(matching), 1)
                face = matching[0]
                declarations = dict(
                    (name.strip().lower(), value.strip())
                    for name, value in (declaration.split(":", 1)
                                        for declaration in face.split(";")
                                        if ":" in declaration)
                )
                prefix, weight = re.fullmatch(r"(.+)-latin-(\d+)-normal\.woff2",
                                             font_file.name).groups()
                family = declarations.get("font-family", "").strip("\"'")
                self.assertEqual(family, families[prefix])
                found_families.add(family)
                self.assertEqual(declarations.get("font-weight"), weight)
                self.assertEqual(declarations.get("font-display"), "swap")
                self.assertRegex(declarations.get("src", ""),
                                 r"format\(\s*['\"]woff2['\"]\s*\)")
        self.assertEqual(found_families, set(families.values()))

    def test_reduced_motion_block_is_present(self):
        self.assertRegex(
            self.css,
            r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{",
        )

    def test_colours_do_not_use_red_or_green(self):
        colours = _COLOUR.findall(self.css)
        self.assertTrue(colours)
        # Tolerance only absorbs binary conversion error at the specified boundaries.
        epsilon = 1e-9
        for colour in colours:
            with self.subTest(colour=colour):
                hue, saturation, lightness = _colour_hsl(colour)
                vivid = saturation >= 40.0 - epsilon and 20.0 - epsilon <= lightness <= 80.0 + epsilon
                banned_hue = any(low - epsilon <= hue <= high + epsilon
                                 for low, high in ((0, 20), (90, 160), (340, 360)))
                self.assertFalse(vivid and banned_hue, "Red or green colour: " + colour)

    def test_golden_pages_link_only_the_local_stylesheet(self):
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
                    expected = "assets/site.css"
                else:
                    self.assertEqual(case["check"], "page")
                    page = apply_edits(_GOLDEN["pages"][case["page"]], case["page_edits"])
                    rendered = render_page(page, index)
                    expected = "../assets/site.css"
                reader = _StylesheetReader()
                reader.feed(rendered)
                reader.close()
                self.assertEqual(reader.stylesheets, [expected])
                rendered_kinds.add(case["check"])
        self.assertEqual(rendered_kinds, {"page", "landing"})


if __name__ == "__main__":
    unittest.main()
