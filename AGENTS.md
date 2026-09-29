# Quant explainer (working title): working instructions for Codex

A static website that explains how an investment has behaved, in plain English, for a
UK retail investor. Descriptive, never advice. It is a CV portfolio piece for product
roles in UK wealth, banking and fintech, judged by hiring managers in under a minute,
often on a phone.

Read before any task: `docs/BRIEF.md` (product and v1 scope), `docs/DECISIONS.md`
(what Avi has confirmed vs what is only proposed), `docs/DATA-RIGHTS.md` (before any
data-related work), `docs/METHODOLOGY.md` (before any calculation-engine work).

## How we work

- Avi is the product owner and is not a developer. He makes product decisions. You make
  routine implementation choices inside the task's scope and explain them in plain English.
- One bounded task at a time. Touch only the files the task names. No unrelated
  refactors, no speculative scaffolding, no new dependencies unless the task allows it.
- If a task hits a product trade-off or an ambiguity that changes what a user sees,
  stop and give options with a recommendation. Do not decide it silently.
- Items marked Proposed in `docs/DECISIONS.md` are not approved. Do not treat anything
  as confirmed because it appears in a doc, a comment or an earlier suggestion.
- Do not commit, push, create branches or change Git configuration. Avi commits.
- Never claim something works without running it. If you could not run a check, say so
  and say why.
- End every task with a report of 150 words or fewer: what changed, what you ran and the
  result, how Avi can check it himself, and anything unresolved.

## Non-negotiable rules

Keys and network
- You never read, request, print, log or store API keys. Keys live outside this folder
  and are loaded by Avi into his own terminal. Scripts read them from environment
  variables only.
- You never run anything that makes a network request. Avi runs those scripts himself.
  You may run offline checks (syntax checks, tests on synthetic data, `--help`/`--list`
  style modes that make no requests).
- Never disable TLS/SSL certificate verification to make a request work. Report the error.

Data rights (see `docs/DATA-RIGHTS.md`)
- Raw provider data (prices, quotes, volumes) is never written to disk, committed,
  cached or logged. Hold it in memory, compute, discard.
- Only derived statistics may be written to files or published: e.g. volatility,
  percentage returns over stated periods, worst/median/best of a distribution,
  correlations. Never publish a price series, a rebased growth/performance line, or any
  output that could reasonably be used to reconstruct the underlying data.
- Tests use synthetic, hand-made data with known answers. Never real provider data.

Numbers and words
- Deterministic Python computes every number. An AI model never does arithmetic.
- Every factual sentence on the site is produced from a fixed template filled with
  computed values. AI-written text (if any) may only refer to computed claims and must
  pass the checks in `docs/BRIEF.md` before publication.
- No advice language anywhere: never "buy", "sell", "should", "attractive", "cheap",
  "safe", "guaranteed", "limited to", "will" (about future outcomes), "recommend".
  Historical results are described as what happened, with dates.

Calculation engine and tests
- `docs/METHODOLOGY.md` is the calculation spec. Code in `engine/` must match it exactly.
  If the spec is unclear or seems wrong, stop and report; do not choose a convention.
- Python standard library only, and code must run on Python 3.9 (Avi's `python3`): no
  `match` statements, no `X | Y` type hints, no third-party packages, no pip installs.
- `engine/` is pure calculation: no file reads or writes, no network, no environment
  variables, no printing or logging of values. It never rounds.
- `tests/golden/` holds expected answers written independently of the code and committed
  by Avi. Never create, edit, rename or delete anything in it. Never produce an expected
  value by running your own code: expected values come from the golden files, or are
  written by hand with the arithmetic shown in a comment. If a golden case fails and you
  think the expected value is wrong, stop and report the case ID and your reasoning. Do
  not bend the code to match, and do not skip the case.
- Run the tests from the repo root with `python3 -m unittest discover -s tests -v`.
- Code organisation: one engine module per methodology section, each with one test file
  `tests/test_<module>.py` and one golden file. Golden tests use the shared helpers in
  `tests/golden_support.py`; never copy them into a test file. If a new kind of check is
  needed, add it there. A rule used by more than one engine module is written once
  (shared rules live in `engine/series.py`) and imported, never re-written.

Data pipeline
- `pipeline/` turns provider responses into engine inputs and published files. Every
  module in it follows the engine's rules (no network, no file reads or writes, no
  environment variables, no printing or logging of values, no rounding) unless a task
  names it as the fetch module or the writer.
- Methodology sections from 7 onward are pipeline sections: one module per section, each
  with one test file `tests/test_<module>.py` and one golden file, using
  `tests/golden_support.py` like the engine.
- Pipeline code reuses engine rules by importing them (month format, series validation,
  errors) and never re-writes them. Do not modify `engine/` in a pipeline task unless
  the task says so.
- Tests never use real provider data and never make network requests. Where fetch code
  must be tested, the test supplies a fake provider in memory.
- `pipeline/network.py` is the only module that may open a network connection. You write
  it but never call it for real: tests replace its `urlopen`. The live fetch is run by
  Avi.
- `pipeline/runner.py` is the only module that writes files, and only in the output
  folder it is given. `scripts/build_data.py` is the command Avi runs; you may run it
  with `--list` (no keys, no requests) but never without it.
- `pipeline/instruments.json` holds hand-checked facts committed by Avi. Treat it like
  `tests/golden/`: never create, edit, rename or delete it. If you think a fact in it is
  wrong, stop and report.

Words
- `words/` turns published documents into card text and claims. It follows the engine's
  rules (no network, no files, no environment variables, no printing) and rounds only
  where METHODOLOGY.md says, once. Sentences are fixed templates: never reword one, add
  one or drop one unless the task and the golden file say so.
- One module per methodology section, one test file and one golden file each, using
  `tests/golden_support.py`.
- `words/context.json` holds hand-checked facts committed by Avi. Treat it like
  `tests/golden/`: never create, edit, rename or delete it.

Site
- The website makes zero runtime API calls. It only reads precomputed JSON.
- Every page shows data sources with attribution and a "data as of" date.
- `scripts/build_pages.py` is the page writer (METHODOLOGY section 14) and the only
  thing that writes `site/data/`. It is offline: no network, no keys, no environment
  variables, no clock. It writes only in the output folder it is given, and its command
  writes only in `site/data`.
- `site/data/` is generated output that Avi commits. Never create, edit or delete
  anything in it by hand, and never run `scripts/build_pages.py` against this repo: the
  tests run it on temporary folders. Avi runs it.
