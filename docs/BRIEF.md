# Brief: quant explainer (working title)

Last updated 28 Sept 2026. Status of each decision lives in `DECISIONS.md`.

## The product in one line

A plain-English explanation of how an investment has behaved and what it would have done
to a portfolio you already hold. Descriptive, never advice. Built to show how a wealth
firm could explain investment risk to clients in a way that is checkable and understood.

## Who it's for

- **Primary:** a UK investor who already holds a global tracker fund and is considering
  one more investment (a large-cap stock, a gold fund, a gilts fund, bitcoin). Their
  question: *"What am I actually getting into, and what does it do to what I already hold?"*
  Account eligibility (ISA or not) is explained separately, not assumed. Direct bitcoin
  and crypto ETNs cannot be newly bought in a Stocks & Shares ISA.
- **Secondary:** junior analysts and non-quants, served by a "show the maths" layer on
  each card.
- **Real first reader:** a hiring manager with 90 seconds.
- The quality bar is set by the retail user. They cannot spot a wrong number.

## Positioning

Not an AI stock analyser. A governed, plain-English client-communication layer for
wealth firms, demonstrated on public assets. Built to run on a firm's licensed data;
the demo uses free sources under their terms. Complements, not replaces, standard risk
indicators: those compress risk into a score; this explains what holding it was like.

## v1 scope

Historical behaviour, stress periods, the effect of holding in pounds, and an
illustrative portfolio comparison. No forecasts. No price charts.

### Landing

A single asset field ("try MSFT"). Supported assets shown as chips; autocomplete only
suggests supported assets; anything else gets a designed "not covered yet" page. Each
asset resolves to one named instrument, shown in full (see Instrument identity).

### Cards (plain-English questions over metrics)

1. **How bumpy is the ride?** Annualised volatility of monthly total returns in GBP,
   next to the global tracker's. Explained as historical variability, not a forecast.
2. **What's the worst it's been?** Largest fall measured at month-end, in % and in £ on
   £10,000. Months from peak to trough, trough to recovery, and total time underwater.
   If not recovered: "not recovered by [date]".
3. **What happened when markets panicked?** Return in fixed stress windows, where
   history covers them. Windows are measured from the month-end before the first month:
   - Global financial crisis: 30 Sep 2007 to 31 Mar 2009
   - Covid crash: 31 Jan 2020 to 31 Mar 2020
   - 2022 rate shock: 31 Dec 2021 to 31 Oct 2022
   An episode's return is not its maximum drawdown; label accordingly.
4. **What did holding it for 1, 3 or 5 years look like?** Distribution of every
   historical holding period of that length: worst, median, best, share of periods that
   lost money, number of periods, date range. Shown as a distribution, never as a line
   over time. States that periods overlap and that the historical worst is not the
   worst possible future result.
5. **What does it do next to a global tracker?** Correlation (full period, and the range
   of rolling 36-month values), plus an illustrative comparison over identical dates:
   100% tracker vs 90% tracker / 10% this asset. Rebalancing rule and fee treatment
   stated. Labelled illustrative, not recommended. For large caps already inside the
   tracker, say so: buying it adds to something already held.
6. **How much of it was the pound?** For non-GBP assets, split the GBP return into the
   local-currency return and the currency return. These compound:
   (1 + GBP return) = (1 + local return) x (1 + currency return).
7. **What these numbers don't capture.** Fixed text per asset type: liquidity, issuer
   or custody risk, product structure, permanent loss, and that past behaviour does not
   predict future results.

Layers: one-line headline read, then the cards, each with a "show the maths" expander
(method, inputs, period, source).

### Out of v1

Forward-looking fan charts or any projection. Fundamental and technical views (the
vision goes in the case study, not the customer journey). Live prices. Daily data.
User accounts. Any "enter any ticker" promise beyond the fixed universe.

## Methodology defaults (v1)

- Simple total returns (dividends reinvested) at month-end. Never mix total-return and
  price-only series. If an instrument only has price data, it is excluded or labelled.
- Volatility: standard deviation of monthly returns x sqrt(12).
- Drawdown on month-end values, labelled "measured at month-end".
- Currency conversion at month-end rates, compounding as above.
- No proxy history: a young fund's history is never extended with an index or another
  share class.

## Instrument identity

Every instrument records: name, ticker, exchange, share class, accumulating or
distributing, currency-hedged or not, trading currency and quote unit (GBP vs pence),
first available date. A physical-gold fund is not spot gold.

## Words: how the text is produced and checked

- **Claims.** Every computed fact is a structured claim: claim ID, instrument, metric,
  period start and end, currency, unit, value, direction, and kind (observed history or
  illustration).
- **Templates.** Every factual sentence is rendered from a claim by a fixed template.
- **AI text (limited).** An AI model may write only the headline read and short
  connective text. It may only refer to claim IDs it is given.
- **Checks before publication**, all in plain code:
  - every number in any text matches a claim's value, unit and currency;
  - no banned language (see `AGENTS.md`);
  - no future-tense statements about outcomes;
  - the claim's instrument, period and kind match how the sentence uses it.
  Anything failing a check is held, not published. A human reviews all AI text before
  publication.
- **Mutation tests.** A suite of deliberately faulty explanations must be blocked, e.g.
  correct drawdown with "your losses would be limited to 35%", a correct number on the
  wrong asset or period, "this is a safe diversifier" with no number.

## Evidence the build must produce

1. **Analytical correctness.** Hand-checkable synthetic examples with known answers,
   edge-case tests, and a cross-check against an independent tool on aligned inputs.
2. **Communication reliability.** The mutation suite passing; source dates, method
   version and review status shown.
3. **Customer understanding.** A small comprehension test (about five people): can they
   explain the loss, recovery, currency and diversification points after using it?
   Measure understanding, not liking.
