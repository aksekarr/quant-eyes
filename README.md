# Quant explainer (working title)

A plain-English explanation of how an investment has behaved, and what it would have
done to a portfolio you already hold. Built for a UK investor holding a developed-world
tracker and considering one more investment. Descriptive, never advice.

Portfolio project by Avi Ravisekara. Built by directing an AI coding agent (Codex) against
written specs and independently written test answers.

## Status

Phase 1: the calculation engine, built and tested on synthetic data only. No real market
data is used or stored yet, and there is no website yet.

## How it's organised

| Path | What it is |
|---|---|
| `engine/` | The calculation engine. Pure Python standard library, no network, no files. Every number the site will show is computed here. |
| `tests/` | Tests that check the engine against the golden answers. |
| `tests/golden/` | Expected answers for small synthetic examples, worked out by hand with the arithmetic written out, independently of the code. |
| `docs/BRIEF.md` | The product: who it's for, what v1 covers, how text is produced and checked. |
| `docs/METHODOLOGY.md` | Exactly how every number is calculated. The code must match it. |
| `docs/DECISIONS.md` | What has been confirmed and what is only proposed. |
| `docs/DATA-RIGHTS.md` | Data-provider terms and the rules that follow from them. |
| `AGENTS.md` | Working rules for the AI coding agent. |
| `pipeline/` | Turns provider data (held in memory only) into engine inputs and derived JSON. |
| `scripts/` | Scripts run by hand that make network requests (currently a data-availability check). |

## Running the tests

From this folder, with Python 3.9 or later and nothing to install:

```
python3 -m unittest discover -s tests -v
```

## Rules that hold everywhere

- **Code computes every number.** An AI model never does arithmetic.
- **Test answers are written independently of the code** and are never edited to make a
  test pass. If code and a golden answer disagree, the disagreement is investigated.
- **Fail closed.** Missing or bad data raises an error; nothing is filled in or guessed.
- **Raw provider data is never stored.** Only derived statistics (returns, volatility,
  drawdowns, correlations) may be written or published, never a price series or growth
  line.
- **No advice.** History is described as what happened, with dates. Nothing forecasts,
  recommends or reassures.
