"""Relational checks on synthetic histories, without generating golden answers."""

import ast
import math
from pathlib import Path
import unittest

from engine.currency import to_gbp
from engine.output import analyse
from engine.portfolio import blend_comparison
from engine.series import MonthlySeries
from golden_support import POUNDS_TOLERANCE_KEYS, assert_result_equal


_TOLERANCE = 1e-9
_POUNDS_TOLERANCE = 1e-6
_SUMMARY_KEYS = (
    "total_return", "annualised_return", "volatility", "largest_fall"
)


def _synthetic_histories():
    """Build consecutive month-ends from August 2007 through August 2026."""
    months = [
        "{:04d}-{:02d}".format(year, month)
        for year in range(2007, 2027)
        for month in range(1, 13)
        if (2007, 8) <= (year, month) <= (2026, 8)
    ]
    # Unequal oscillations plus a trend give positive, nonrepeating histories
    # with rises and falls. Decimal offsets avoid simple raw-value coincidences.
    tracker_values = [
        143.726419 + 0.431729 * i
        + 13.217643 * math.sin(0.43 * i)
        + 7.514239 * math.cos(0.17 * i)
        for i in range(len(months))
    ]
    asset_values = [
        257.983671 + 0.673219 * i
        + 37.281493 * math.sin(0.31 * i + 0.27)
        + 18.917423 * math.cos(0.11 * i + 0.43)
        for i in range(len(months))
    ]
    fx_values = [
        1.583729 + 0.000173 * i
        + 0.137491 * math.sin(0.23 * i + 0.71)
        + 0.071359 * math.cos(0.07 * i + 0.39)
        for i in range(len(months))
    ]
    tracker = MonthlySeries.from_pairs(
        "Synthetic tracker", "GBP", "total_return", zip(months, tracker_values)
    )
    asset = MonthlySeries.from_pairs(
        "Synthetic asset", "USD", "total_return", zip(months, asset_values)
    )
    fx = MonthlySeries.from_pairs(
        "Synthetic GBP/USD", "USD", "fx_rate", zip(months, fx_values)
    )
    return asset, tracker, fx


def _scaled(series, factor):
    return MonthlySeries.from_pairs(
        series.name, series.currency, series.basis,
        [(month, value * factor) for month, value in zip(series.months, series.values)],
    )


def _slice(series, start=None, end=None):
    return MonthlySeries.from_pairs(
        series.name, series.currency, series.basis,
        zip(series.months[start:end], series.values[start:end]),
    )


def _summary(profile):
    return {key: profile[key] for key in _SUMMARY_KEYS}


class InvarianceTests(unittest.TestCase):
    def setUp(self):
        self.asset, self.tracker, self.fx = _synthetic_histories()
        for series in (self.asset, self.tracker, self.fx):
            self.assertEqual(series.first_month, "2007-08")
            self.assertEqual(series.last_month, "2026-08")
            self.assertTrue(all(value > 0.0 for value in series.values))
            adjacent = list(zip(series.values, series.values[1:]))
            self.assertTrue(any(after > before for before, after in adjacent))
            self.assertTrue(any(after < before for before, after in adjacent))

        self.result = analyse(self.asset, self.tracker, self.fx)
        side = self.result["side_by_side"]
        # Prevent empty results from making an invariance assertion vacuous.
        for profile in (self.result["own"], side["asset"], side["tracker"]):
            self.assertIsNotNone(profile)
            self.assertEqual(
                [window["window"] for window in profile["stress_windows"]],
                ["gfc", "covid", "rate_shock"],
            )
            for window in profile["stress_windows"]:
                self.assertIs(window["covered"], True)
                self.assertIsNotNone(window["return"])
            for horizon, months in (("1_year", 12), ("3_years", 36), ("5_years", 60)):
                holding = profile["holding_periods"][horizon]
                self.assertIsNotNone(holding)
                # Section 4.2: N observations give N - horizon holding periods.
                self.assertEqual(holding["periods"], len(self.asset.months) - months)
            self.assertGreater(profile["volatility"], 0.0)
            self.assertLess(profile["largest_fall"]["max_drawdown"], 0.0)
        self.assertIsNotNone(side["correlation"])
        self.assertIsNotNone(side["rolling_correlation_36"])
        # N observations -> N - 1 returns -> (N - 1) - 36 + 1 runs.
        self.assertEqual(
            side["rolling_correlation_36"]["windows"], len(self.asset.months) - 36
        )
        self.assertIsNotNone(side["blend_90_10"])
        self.assertIsNotNone(self.result["currency"]["full_history"])
        for window in self.result["currency"]["stress_windows"]:
            self.assertIs(window["covered"], True)

    def _compare(self, actual, expected):
        assert_result_equal(
            self, actual, expected, _TOLERANCE,
            POUNDS_TOLERANCE_KEYS, _POUNDS_TOLERANCE,
        )

    def test_asset_quote_unit_scaling_leaves_output_unchanged(self):
        # Exercise the USD conversion path and the GBP-to-pence quote-unit case.
        for asset, fx in ((self.asset, self.fx), (to_gbp(self.asset, self.fx), None)):
            with self.subTest(currency=asset.currency):
                self._compare(
                    analyse(_scaled(asset, 100.0), self.tracker, fx),
                    analyse(asset, self.tracker, fx),
                )

    def test_tracker_pence_scaling_leaves_output_unchanged(self):
        self._compare(
            analyse(self.asset, _scaled(self.tracker, 100.0), self.fx), self.result
        )

    def test_constant_fx_scaling_leaves_output_and_currency_identity_unchanged(self):
        scaled_result = analyse(self.asset, self.tracker, _scaled(self.fx, 1.1))
        # No exported field changes, including currency_return in full_history
        # and every stress window: (c * FX_start) / (c * FX_end) cancels c.
        # Local returns do not use FX. GBP levels become V_GBP / c, so all GBP
        # return ratios, risks, correlations, holdings and blend figures agree.
        # Raw converted levels would change, but they are never exported.
        self._compare(scaled_result, self.result)
        for label, result in (("original", self.result), ("scaled", scaled_result)):
            currency = result["currency"]
            splits = [currency["full_history"]] + currency["stress_windows"]
            pound_returns = [result["own"]["total_return"]] + [
                window["return"] for window in result["own"]["stress_windows"]
            ]
            for split, pound_return in zip(splits, pound_returns):
                with self.subTest(rates=label, start=split["start"], end=split["end"]):
                    self._compare(
                        1.0 + split["gbp_return"],
                        (1.0 + split["local_return"]) * (1.0 + split["currency_return"]),
                    )
                    self._compare(split["gbp_return"], pound_return)

    def test_tracker_against_itself_has_identical_profiles_and_blend(self):
        result = analyse(self.tracker, self.tracker)
        side = result["side_by_side"]
        self._compare(side["correlation"], 1.0)
        for key in ("lowest", "highest"):
            self._compare(side["rolling_correlation_36"][key], 1.0)
        self._compare(side["asset"], side["tracker"])
        self._compare(result["own"], side["tracker"])
        comparison = side["blend_90_10"]
        self._compare(comparison["asset_weight"], 0.1)
        self._compare(comparison["tracker"], _summary(side["tracker"]))
        self._compare(comparison["blend"], _summary(side["tracker"]))

    def test_blend_weight_boundaries_equal_common_month_profiles(self):
        pound_asset = to_gbp(self.asset, self.fx)
        cases = (
            ("full", pound_asset, self.tracker),
            # The asset ends earlier and the tracker starts later, so each
            # input must be trimmed at a different end of the common window.
            ("staggered", _slice(pound_asset, end=-5), _slice(self.tracker, start=7)),
        )
        for label, asset, tracker in cases:
            side = analyse(asset, tracker)["side_by_side"]
            for weight, profile_name in ((0.0, "tracker"), (1.0, "asset")):
                with self.subTest(history=label, asset_weight=weight):
                    comparison = blend_comparison(tracker, asset, asset_weight=weight)
                    self._compare(
                        {key: comparison[key] for key in ("start", "end", "months")},
                        {
                            "start": max(asset.first_month, tracker.first_month),
                            "end": min(asset.last_month, tracker.last_month),
                            "months": len(set(asset.months) & set(tracker.months)) - 1,
                        },
                    )
                    self._compare(comparison["asset_weight"], weight)
                    self._compare(comparison["tracker"], _summary(side["tracker"]))
                    self._compare(comparison["blend"], _summary(side[profile_name]))

    def test_repeated_analysis_is_identical(self):
        repeated = analyse(self.asset, self.tracker, self.fx)
        self._compare(repeated, self.result)
        # Repeatability is stricter than numerical closeness: values agree exactly.
        self.assertEqual(repeated, self.result)

    def test_no_output_float_equals_a_raw_input_value(self):
        input_values = set(self.asset.values + self.tracker.values + self.fx.values)
        pending = [("result", self.result)]
        checked = 0
        while pending:
            path, value = pending.pop()
            if isinstance(value, dict):
                pending.extend((path + "." + key, child) for key, child in value.items())
            elif isinstance(value, list):
                pending.extend(
                    ("{}[{}]".format(path, index), child)
                    for index, child in enumerate(value)
                )
            elif type(value) is float:
                checked += 1
                # Exact membership is evidence against raw-value leakage, not
                # a proof against every possible reconstruction of an input.
                self.assertFalse(value in input_values, "Raw input float at " + path)
        self.assertGreater(checked, 0)

    def test_engine_sources_have_no_io_imports_or_calls(self):
        root = Path(__file__).resolve().parents[1]
        source_paths = sorted((root / "engine").glob("*.py"))
        self.assertTrue(source_paths)
        forbidden_imports = {
            "socket", "urllib", "http", "requests", "os", "pathlib", "io",
            "shutil", "subprocess",
        }
        # Keep the import boundary closed to other I/O-capable modules too.
        # New standard-library imports need explicit review of this allowlist.
        allowed_imports = {"math", "numbers", "re", "statistics", "engine"}
        allowed_imports.update("engine." + path.stem for path in source_paths)
        allowed_pipeline_imports = {
            "monthly.py": {"calendar", "datetime", "math", "numbers", "re", "engine.series"},
            "publish.py": {
                "copy", "datetime", "math", "numbers", "re",
                "engine.output", "engine.series",
            },
            "providers.py": {"re", "engine.series"},
        }
        source_paths.extend(root / "pipeline" / name for name in allowed_pipeline_imports)
        allowed_words_imports = {
            "cards.py": {"decimal", "math", "numbers", "re", "engine.series"},
            "cards_567.py": {
                "decimal", "math", "numbers", "re", "engine.series", "words.cards",
            },
            "headline.py": {"copy", "json", "re", "pipeline.publish", "words.cards"},
            "page.py": {"copy", "pipeline.publish", "words.cards", "words.cards_567"},
        }
        source_paths.extend(root / "words" / name for name in allowed_words_imports)
        for path in source_paths:
            package = path.parent.name
            if package == "engine":
                module_allowlist = allowed_imports
            elif package == "pipeline":
                module_allowlist = allowed_pipeline_imports[path.name]
            else:
                module_allowlist = allowed_words_imports[path.name]
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                with self.subTest(module=path.name, line=getattr(node, "lineno", None)):
                    imports = []
                    if isinstance(node, ast.Import):
                        imports = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if node.level:
                            self.assertEqual(node.level, 1)
                            module = package + ("." + module if module else "")
                        imports = [module]
                    for module in imports:
                        self.assertNotIn(module.split(".")[0], forbidden_imports)
                        self.assertIn(module, module_allowlist)
                    if isinstance(node, ast.Call):
                        function = node.func
                        if isinstance(function, ast.Name):
                            self.assertNotIn(function.id, {"open", "print", "__import__", "eval", "exec"})
                        elif isinstance(function, ast.Attribute):
                            self.assertNotIn(function.attr, {"open", "print", "__import__", "eval", "exec"})

        self._check_network_source(root / "pipeline" / "network.py")
        self._check_file_io_source(
            root / "pipeline" / "runner.py",
            {
                "datetime", "json", "os", "engine.output", "engine.series",
                "pipeline.monthly", "pipeline.providers", "pipeline.publish",
            },
            {"print", "eval", "exec", "__import__"},
        )
        self._check_file_io_source(
            root / "scripts" / "build_data.py",
            {
                "datetime", "json", "os", "pathlib", "sys", "time",
                "pipeline.monthly", "pipeline.network", "pipeline.providers",
                "pipeline.publish", "pipeline.runner",
            },
            {"eval", "exec", "__import__"},
        )
        pages_path = root / "scripts" / "build_pages.py"
        self._check_file_io_source(
            pages_path,
            {"json", "os", "pathlib", "sys", "pipeline.publish", "words.cards", "words.page"},
            {"eval", "exec", "__import__", "getenv"},
        )
        self.assertNotIn(".environ", pages_path.read_text(encoding="utf-8"))
        self._check_file_io_source(
            root / "scripts" / "draft_headlines.py",
            {
                "datetime", "json", "os", "pathlib", "re", "sys",
                "pipeline.network", "pipeline.providers", "pipeline.publish",
                "words.cards", "words.headline",
            },
            {"eval", "exec", "__import__"},
        )

    def _check_file_io_source(self, path, allowed_imports, forbidden_calls):
        """Keep the writer and command within their explicit I/O boundaries."""
        forbidden_imports = {"urllib", "socket", "http", "subprocess", "shutil"}
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            with self.subTest(module=path.name, line=getattr(node, "lineno", None)):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if node.level:
                        self.assertEqual(node.level, 1)
                        module = path.parent.name + ("." + module if module else "")
                    imports = [module]
                for module in imports:
                    self.assertNotIn(module.split(".")[0], forbidden_imports)
                    self.assertIn(module, allowed_imports)
                if isinstance(node, ast.Call):
                    function = node.func
                    if isinstance(function, ast.Name):
                        self.assertNotIn(function.id, forbidden_calls)
                    elif isinstance(function, ast.Attribute):
                        self.assertNotIn(function.attr, forbidden_calls)

    def _check_network_source(self, path):
        """Check the connection module's separate, deliberately narrow boundary."""
        source = path.read_text(encoding="utf-8")
        allowed_imports = {
            "json", "socket", "urllib.request", "urllib.error", "pipeline.providers",
        }
        forbidden_calls = {"open", "print", "eval", "exec", "__import__"}
        with self.subTest(module=path.name):
            for forbidden_text in (
                "_create_unverified_context", "CERT_NONE", "check_hostname",
            ):
                self.assertNotIn(forbidden_text, source)
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            with self.subTest(module=path.name, line=getattr(node, "lineno", None)):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if node.level:
                        self.assertEqual(node.level, 1)
                        module = "pipeline" + ("." + module if module else "")
                    imports = [module]
                for module in imports:
                    self.assertIn(module, allowed_imports)
                if isinstance(node, ast.Call):
                    function = node.func
                    if isinstance(function, ast.Name):
                        self.assertNotIn(function.id, forbidden_calls)
                    elif isinstance(function, ast.Attribute):
                        self.assertNotIn(function.attr, forbidden_calls)
                    self.assertTrue(
                        all(keyword.arg != "context" for keyword in node.keywords)
                    )


if __name__ == "__main__":
    unittest.main()
