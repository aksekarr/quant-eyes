"""Golden guided copy, full page read-back and disclosure structure checks."""

from copy import deepcopy
import unittest

from golden_support import (
    apply_edits, assert_result_equal, generate_golden_tests, load_golden,
)
import test_site_render as site_render_tests
from web.render import SiteError, render_page
from words.cards import WordsError
from words.guided import build_guided


_GOLDEN = load_golden("guided.json")


class GuidedGoldenTests(unittest.TestCase):
    # Reuse the complete section 16.7 checks without inheriting renderer tests.
    assert_markup = site_render_tests.SiteRenderGoldenTests.assert_markup
    assert_structure = site_render_tests.SiteRenderGoldenTests.assert_structure
    assert_link = site_render_tests.SiteRenderGoldenTests.assert_link

    def exercise_case(self, case):
        if case["check"] == "build_guided":
            page = apply_edits(_GOLDEN["pages"][case["page"]], case["page_edits"])
            facts = apply_edits(_GOLDEN["facts"][case["page"]], case["facts_edits"])
            inputs = (page, facts)
            operation = lambda: build_guided(page, facts)
            error_type = WordsError
        else:
            page = deepcopy(_GOLDEN["fixture_pages"][case["fixture"]])
            page["guided"] = apply_edits(
                build_guided(page, deepcopy(case["facts"])), case["guided_edits"],
            )
            index = deepcopy(_GOLDEN["index"])
            inputs = (page, index)
            operation = lambda: render_page(page, index)
            error_type = SiteError

        original_inputs = deepcopy(inputs)
        outputs = []
        for repeat in range(2):
            with self.subTest(repeat=repeat + 1):
                if "expected_error" in case:
                    with self.assertRaises(error_type) as raised:
                        operation()
                    self.assertIs(type(raised.exception), error_type)
                    self.assertEqual(str(raised.exception), case["expected_error"])
                else:
                    result = operation()
                    if case["check"] == "build_guided":
                        assert_result_equal(self, result, case["expected"], tolerance=0)
                    else:
                        self.assertIs(type(result), str)
                        reader = site_render_tests._PageReader()
                        reader.feed(result)
                        reader.close()
                        self.assert_markup(result, reader, index, [page], False)
                        self.assertEqual(reader.entries(), case["expected"])
                        self.assert_structure(reader, index, [page], False)
                        self.assert_guided_structure(reader, page)
                    outputs.append(result)
                self.assertEqual(inputs, original_inputs)
        if "expected_error" not in case:
            self.assertEqual(len(outputs), 2)
            self.assertEqual(outputs[0], outputs[1])

    def assert_guided_structure(self, reader, page):
        """Each card ends in one closed disclosure with the specified headings."""
        entries = {
            (element["attrs"]["data-qx"], element["attrs"].get("data-qx-key", "")): element
            for element in reader.elements
            if "data-qx" in element["attrs"]
        }
        for step in page["guided"]["steps"]:
            card_id = step["card"]
            opener = entries[("more-open", card_id)]
            summary = (
                opener if opener["tag"] == "summary"
                else site_render_tests._ancestor(opener, "summary")
            )
            self.assertIsNotNone(summary)
            details = site_render_tests._ancestor(summary, "details")
            self.assertIsNotNone(details)
            self.assertNotIn("open", details["attrs"])
            section = site_render_tests._ancestor(details, "section")
            self.assertIsNotNone(section)
            self.assertEqual(section["attrs"].get("id"), card_id)

            descendants = [
                element for element in reader.elements
                if any(details is ancestor for ancestor in element["ancestors"])
            ]
            self.assertIs(descendants[0], summary)
            self.assertEqual(sum(item["tag"] == "summary" for item in descendants), 1)
            for role in ("everyday-label", "everyday"):
                self.assertTrue(any(
                    entries[(role, card_id)] is element for element in descendants
                ))
            for number, panel in enumerate(step["more"], 1):
                key = "{}.{}".format(card_id, number)
                self.assertEqual(entries[("more-title", key)]["tag"], "h3")
                for role in ("more-number", "more-title", "more-text"):
                    self.assertTrue(any(
                        entries[(role, key)] is element for element in descendants
                    ))

            # Nothing in the card follows the disclosure, even when it is wrapped
            # in the existing next/pound phone accordion body.
            card_elements = [
                element for element in reader.elements
                if any(section is ancestor for ancestor in element["ancestors"])
            ]
            self.assertIs(card_elements[-1], descendants[-1])
            self.assertIsNone(site_render_tests._ancestor(details, "details"))


generate_golden_tests(
    GuidedGoldenTests, _GOLDEN["cases"], {"build_guided", "render_page"},
)


if __name__ == "__main__":
    unittest.main()
