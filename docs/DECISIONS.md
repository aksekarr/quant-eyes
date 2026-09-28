# Decisions

Only Avi confirms decisions. Anything under Proposed is not approved.

## Confirmed

| Date | Decision | Why |
|---|---|---|
| 2026-09-28 | Portfolio piece, not a commercial product. Descriptive, never advice. | Demonstrates judgment for wealth/fintech PM roles without regulatory exposure. |
| 2026-09-28 | Primary user: UK investor holding a global tracker, considering one more investment. Base currency GBP; benchmark a global tracker in GBP. | Gives every card a concrete question and a comparison point. |
| 2026-09-28 | Positioning: governed plain-English client-communication layer for wealth firms, demonstrated on public assets. | Stats are commoditised; trustworthy explanation is the gap. |
| 2026-09-28 | Universe: the funds a UK investor would actually buy (London-listed, GBP) plus large caps held directly, plus bitcoin. Spot/benchmark gold excluded. | Matches the persona; gold benchmark data is actively licensed. |
| 2026-09-28 | Landing page is a single asset field with supported-asset chips and a designed "not covered yet" state. | One gesture shows the whole idea; no dead ends. |
| 2026-09-28 | Long horizons, monthly data. No live prices, no red/green trading styling. | Avoids "trade now" signals; fits the data posture. |
| 2026-09-28 | No forward-looking fan chart in v1. Replaced by the historical holding-period distribution card. | Resampled history is not a defensible projection; observed outcomes are honest. |
| 2026-09-28 | Fundamental and technical views removed from the customer journey; the vision goes in the case study. | Analyst jargon for a retail user; the question-led cards are the structure. |
| 2026-09-28 | Deterministic code computes every number; factual sentences come from templates; AI text is limited, checked in code and human-reviewed. | A number check alone cannot catch a correct number used misleadingly. |
| 2026-09-28 | Raw provider data never stored; only derived statistics published; no price or growth charts. | Provider terms (see DATA-RIGHTS.md). |
| 2026-09-28 | Comprehension test with about five people is part of the build. | Evidence of understanding, not just design. |
| 2026-09-28 | Codex never handles API keys or runs network scripts; Avi runs them. | Structural control, not a written request (lesson from BBB). |
| 2026-09-28 | Benchmark: SWDA.LON (iShares Core MSCI World, accumulating, GBP line), labelled a developed-world tracker, not global. | Longest London tracker history (from Dec 2009); accumulating, so no reliance on the provider's dividend adjustment. Cost: excludes emerging markets. |
| 2026-09-28 | Universe (8): SWDA.LON benchmark; MSFT, AAPL, NVDA; SGLN.LON (physical gold); IGLT.LON (UK gilts); AZN.LON (AstraZeneca); bitcoin. US-listed ETFs (VT, IAU, GLD) dropped. | Data check 28 Sept: all available with no quality flags. US-listed ETFs are generally not buyable by UK retail. AstraZeneca over Shell: one continuous share line (Shell's 2022 share unification means stitched history). |
| 2026-09-28 | Bitcoin included, history from Jan 2015. The page never presents the four-year cycle as a pattern. | Shows the product handling a short, regime-dominated history honestly. Pre-2015 data is Mt Gox era. About three halving cycles is three observations, not evidence. |
| 2026-09-28 | Data providers: Tiingo (US stocks, bitcoin) and Alpha Vantage (London funds and stocks, GBP/USD), free tiers. GBP/USD from Aug 2007, so GBP history of US assets starts there. | Both covered the universe in the data check. Alpha Vantage terms don't address public display: email them before any public release. |
| 2026-09-28 | Calculation engine uses the Python standard library only and runs on Python 3.9. | Nothing to install; no silent date-matching or blank-skipping; every formula explicit for "show the maths". An independent checker can use pandas later. |
| 2026-09-28 | Expected test answers are written in `tests/golden/` independently of the code (by Claude), committed by Avi before Codex runs, and never edited by Codex. | Tests written by the code's author only prove the code agrees with itself. `git status --short` shows any edit. |
| 2026-09-28 | Engine foundation conventions (METHODOLOGY.md section 1): series matched by calendar month; any gap, duplicate, zero, negative or non-numeric value rejects the series; nothing under 12 months is annualised; the engine never rounds; error messages never show a value. | Fail closed rather than guess; one rounding per displayed number; raw values never reach logs. |
| 2026-09-28 | Volatility uses the sample standard deviation (divide by n − 1), annualised by x sqrt(12). | The convention in Excel STDEV.S and pandas, and what an independent cross-check will assume. |
| 2026-09-28 | Every comparison with the tracker uses identical months (the common window). The asset's own full-history figures are shown separately where relevant. | Comparing an asset measured through 2008 with a tracker that skipped it would flatter the tracker. SWDA starts Dec 2009, so US assets' side-by-side starts Jan 2010 and no tracker figure exists for the GFC window. |
| 2026-09-28 | Largest-fall conventions (METHODOLOGY.md section 3.2): measured at month-end; the first month counts as a high; on a tie the earliest trough; the peak is the last month at the high; recovery means back at or above the peak; underwater is elapsed months from peak to recovery; the £ figure applies only to £10,000 invested at the high; an unrecovered fall is stated as "not recovered by [month], still X% below its high", never as a forecast. | Each is a place where a plausible-looking number could mislead; fixing them in writing makes the card checkable. |
| 2026-09-28 | Stress-window and holding-period conventions (METHODOLOGY.md section 4): a window is covered only if both its end months exist, never shortened; a window's return is described as "over the period", not as a fall; N month-end values give N − h holding periods of h months, of which (N − 1) ÷ h (rounded down) do not overlap; horizons are whole years; ties go to the earliest start; "lost money" means below zero; totals and per-year figures are both computed and the display choice is made later. | Fence-post and overlap errors are the easiest way to overstate the evidence; fixing the definitions makes the card checkable. |

## Proposed (not approved)

| Proposal | Notes |
|---|---|
| Show a holding-period horizon only if history covers at least 3 non-overlapping periods of that length (e.g. 15 years for 5-year periods). | Bitcoin would show 1- and 3-year only. |
| 90/10 comparison rebalanced annually, before fees. | Needs a stated rule; annual is simple and realistic. |
| AI provider and model for the headline read. | Unresolved. |
| Ethereum deferred to after v1. | Adds little the bitcoin card doesn't already show; shorter history; 2022 proof-of-stake switch and staking yield complicate what 'total return' means. Adding it later is one config line once the pipeline exists. |
| Product name. | Working title only. |
