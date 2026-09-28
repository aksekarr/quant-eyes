# Quant explainer (working title): working instructions for Codex

A static website that explains how an investment has behaved, in plain English, for a
UK retail investor. Descriptive, never advice. It is a CV portfolio piece for product
roles in UK wealth, banking and fintech, judged by hiring managers in under a minute,
often on a phone.

Read before any task: `docs/BRIEF.md` (product and v1 scope), `docs/DECISIONS.md`
(what Avi has confirmed vs what is only proposed), `docs/DATA-RIGHTS.md` (before any
data-related work).

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

Site
- The website makes zero runtime API calls. It only reads precomputed JSON.
- Every page shows data sources with attribution and a "data as of" date.
