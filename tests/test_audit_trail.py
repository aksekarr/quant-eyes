"""Golden read-back, review validation and hidden audit drawer checks."""

from copy import deepcopy
import unittest

from golden_support import apply_edits, generate_golden_tests, load_golden
import test_site_render as site_render_tests
from web.render import SiteError, check_reviews, render_landing


_GOLDEN = load_golden("audit_trail.json")
_PAGES_BY_ID = {
    page["instrument"]["id"]: page for page in _GOLDEN["pages"].values()
}


class AuditTrailGoldenTests(unittest.TestCase):
    # Reuse the renderer's complete section 16.7 checks without inheriting its tests.
    assert_markup = site_render_tests.SiteRenderGoldenTests.assert_markup
    assert_structure = site_render_tests.SiteRenderGoldenTests.assert_structure
    assert_link = site_render_tests.SiteRenderGoldenTests.assert_link

    def exercise_case(self, case):
        index = apply_edits(_GOLDEN["index"], case["index_edits"])
        pages = [
            apply_edits(
                _PAGES_BY_ID[asset["id"]],
                case["page_edits"].get(asset["id"], []),
            )
            for asset in index["assets"]
        ]
        reviews = (
            deepcopy(case["reviews_value"])
            if "reviews_value" in case
            else apply_edits(_GOLDEN["reviews"], case["review_edits"])
        )
        inputs = (index, pages, reviews)
        original_inputs = deepcopy(inputs)
        outputs = []
        for repeat in range(2):
            with self.subTest(repeat=repeat + 1):
                if "expected_error" in case:
                    for name, operation in (
                        ("check_reviews", lambda: check_reviews(reviews, index, pages)),
                        ("render_landing", lambda: render_landing(index, pages, reviews)),
                    ):
                        with self.subTest(operation=name):
                            with self.assertRaises(SiteError) as raised:
                                operation()
                            self.assertIs(type(raised.exception), SiteError)
                            self.assertEqual(str(raised.exception), case["expected_error"])
                            self.assertEqual(inputs, original_inputs)
                else:
                    check_reviews(reviews, index, pages)
                    self.assertEqual(inputs, original_inputs)
                    rendered = render_landing(index, pages, reviews)
                    self.assertIs(type(rendered), str)
                    reader = site_render_tests._PageReader()
                    reader.feed(rendered)
                    reader.close()
                    self.assert_markup(rendered, reader, index, pages, True)
                    self.assertEqual(reader.entries(), case["expected"])
                    self.assertEqual(
                        [
                            element["attrs"]["data-trail"]
                            for element in reader.elements
                            if "data-trail" in element["attrs"]
                        ],
                        case["expected_targets"],
                    )
                    self.assert_structure(reader, index, pages, True)
                    self.assert_audit_structure(reader, index, pages)
                    outputs.append(rendered)
                self.assertEqual(inputs, original_inputs)
        if "expected_error" not in case:
            self.assertEqual(len(outputs), 2)
            self.assertEqual(outputs[0], outputs[1])

    def assert_audit_structure(self, reader, index, pages):
        """Check section 16.9's buttons, dialog semantics and hidden placement."""
        entries = {
            (element["attrs"]["data-qx"], element["attrs"].get("data-qx-key", "")): element
            for element in reader.elements
            if "data-qx" in element["attrs"]
        }
        positions = {id(element): number for number, element in enumerate(reader.elements)}
        asset_ids = [asset["id"] for asset in index["assets"]]
        openers = [
            element for element in reader.elements if "data-trail" in element["attrs"]
        ]
        for opener in openers:
            self.assertEqual(opener["tag"], "button")
            self.assertEqual(opener["attrs"].get("type"), "button")
            self.assertEqual(opener["attrs"].get("aria-haspopup"), "dialog")
            self.assertIn(opener["attrs"]["data-trail"], asset_ids)
            self.assertNotIn("data-qx", opener["attrs"])
            self.assertIsNone(site_render_tests._ancestor(opener, "button"))

        for page in pages:
            if page["headline"] is None:
                continue
            asset_id = page["instrument"]["id"]
            button = site_render_tests._ancestor(entries[("audit-open", asset_id)], "button")
            self.assertIsNotNone(button)
            self.assertEqual(button["attrs"].get("data-trail"), asset_id)
            for role in ("audit-drafted", "audit-checked", "audit-reviewed"):
                self.assertIs(
                    site_render_tests._ancestor(entries[(role, asset_id)], "button"),
                    button,
                )
        gate = entries[("gate-open", "03")]
        gate_button = site_render_tests._ancestor(gate, "button")
        self.assertIsNotNone(gate_button)
        self.assertTrue(any(gate_button is opener for opener in openers))
        self.assertGreater(positions[id(gate_button)], positions[id(entries[("gate-text", "03")])])

        dialogs = [
            element for element in reader.elements if element["attrs"].get("role") == "dialog"
        ]
        self.assertEqual(
            [dialog["attrs"].get("id") for dialog in dialogs],
            ["trail-" + asset_id for asset_id in asset_ids],
        )
        # All drawers share one hidden holder outside main and before the footer.
        common_holders = [
            ancestor
            for ancestor in dialogs[0]["ancestors"]
            if "hidden" in ancestor["attrs"]
            and all(
                any(ancestor is parent for parent in dialog["ancestors"])
                for dialog in dialogs
            )
        ]
        self.assertTrue(common_holders)
        holder = common_holders[-1]
        self.assertIsNone(site_render_tests._ancestor(holder, "main"))
        self.assertIsNone(site_render_tests._ancestor(holder, "footer"))
        main_end = max(
            positions[id(element)]
            for element in reader.elements
            if element["tag"] == "main"
            or site_render_tests._ancestor(element, "main") is not None
        )
        footer_start = min(
            positions[id(element)] for element in reader.elements if element["tag"] == "footer"
        )
        self.assertGreater(positions[id(holder)], main_end)
        self.assertLess(positions[id(holder)], footer_start)

        for asset_id, dialog in zip(asset_ids, dialogs):
            attrs = dialog["attrs"]
            self.assertEqual(attrs.get("aria-modal"), "true")
            self.assertEqual(attrs.get("aria-labelledby"), "trail-title-" + asset_id)
            self.assertIn("hidden", attrs)
            self.assertLess(positions[id(dialog)], footer_start)
            title = entries[("trail-title", asset_id)]
            self.assertEqual(title["tag"], "h2")
            self.assertEqual(title["attrs"].get("id"), attrs["aria-labelledby"])
            self.assertEqual(entries[("trail-earlier", asset_id)]["tag"], "h3")
            close = entries[("trail-close", asset_id)]
            self.assertEqual(close["tag"], "button")
            self.assertEqual(close["attrs"].get("data-qx-attr"), "aria-label")
            self.assertEqual(close["attrs"].get("aria-label"), "Close the audit trail")
            self.assertEqual("".join(close["text"]), "")
            for (role, key), element in entries.items():
                if role.startswith("trail-") and (key == asset_id or key.startswith(asset_id + ".")):
                    self.assertTrue(any(dialog is ancestor for ancestor in element["ancestors"]))

        for element in reader.elements:
            attrs = element["attrs"]
            if "aria-haspopup" in attrs:
                self.assertIn("data-trail", attrs)
                self.assertEqual(attrs["aria-haspopup"], "dialog")
            if "aria-modal" in attrs or "aria-labelledby" in attrs:
                self.assertEqual(attrs.get("role"), "dialog")


generate_golden_tests(
    AuditTrailGoldenTests,
    [
        dict(case, check="error" if "expected_error" in case else "render")
        for case in _GOLDEN["cases"]
    ],
    {"render", "error"},
)


if __name__ == "__main__":
    unittest.main()
