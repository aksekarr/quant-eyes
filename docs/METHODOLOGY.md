# Methodology: how every number is calculated

This is the calculation spec for the engine (`engine/`). The code must match it exactly.
The worked examples for each section live in `tests/golden/*.json`. They were written
by hand, independently of the code, and the tests check the code against them. The
"show the maths" text on the site will be drawn from this document.

Whether a convention is confirmed or only proposed is recorded in `DECISIONS.md`. A
section is written here only once its conventions are confirmed.

| Section | Engine task | Golden file | Status |
|---|---|---|---|
| 1. Monthly series and returns | 1 | `foundation.json` | Written |
| 2. Currency | 2 | `currency.json` | Written |
| 3. Volatility and largest fall | 3 | `risk.json` | Written |
| 4. Stress windows and holding periods | 4 | `windows.json` | Written |
| 5. Correlation and the 90/10 comparison | 5 | `portfolio.json` | Written |
| 6. Engine output | 6 | `output.json` | Written |
| 7. From provider rows to month-end values | Pipeline 1 | `monthly.json` | Written |

## General rules

- **Standard library only**, runs on Python 3.9 or later. No third-party packages.
- **Pure calculation.** The engine reads no files, makes no network requests and reads
  no environment variables. Data arrives in memory and derived numbers leave in memory.
- **The engine never rounds.** It returns full-precision values. Rounding for display
  happens once, in the claims layer, so every displayed number has exactly one rounding.
- **Fail closed.** Bad or incomplete input raises an error. The engine never fills,
  interpolates, skips or guesses a missing value.
- **Error messages name the month and the problem, never the value.** Raw provider
  values must not reach logs or the terminal (see `DATA-RIGHTS.md`).

## 1. Monthly series and returns

### 1.1 The monthly series

A monthly series is an ordered run of month-end values for one instrument.

- **Month keys.** Months are written `YYYY-MM` (e.g. `2020-03`). A value at `2020-03` is
  the value at the end of March 2020: the last available close in that month. Series from
  different providers are matched by calendar month, not by exact date, because the last
  trading day differs between markets and data sources (a US stock and an exchange rate
  can close March on different days).
- **Labels.** Every series carries:
  - `name`: free text for humans.
  - `currency`: a three-letter upper-case code (`GBP`, `USD`). Pence-quoted London lines
    are labelled `GBP`. Returns are ratios, so the quote unit cancels out; the unit is
    recorded in instrument identity, not in the engine.
  - `basis`: one of `total_return` (dividends reinvested), `price` (price only) or
    `fx_rate` (an exchange rate). Later sections refuse to mix bases.
- **Validation.** A series is rejected with `SeriesError` if any of these hold:
  - fewer than 2 observations;
  - a month key that isn't `YYYY-MM` with a month from 01 to 12;
  - a duplicate month, a month out of ascending order, or a gap (a missing month). For
    a gap, the message names the first missing month;
  - a value that isn't an ordinary number (a string, a true/false value, empty);
  - a value that is not finite (NaN, infinity) or is zero or negative;
  - a currency that isn't three upper-case letters, or an unknown basis.
- Once built, a series cannot be changed.

### 1.2 Monthly returns

The simple return in month *m* is

    r(m) = V(m) / V(m − 1) − 1

and is labelled with month *m*, the month it ends in. A series of *n* values has *n − 1*
monthly returns; the first month has no return.

Example: 100 → 110 → 99 → 118.8 gives +10%, −10%, +20%. Note that +10% followed by −10%
leaves 99, not 100.

### 1.3 Return between two month-ends

The return from the end of month *s* to the end of month *e* is

    R = V(e) / V(s) − 1

A period is measured **from the month-end before its first month**. For example, the
2022 rate-shock window "31 Dec 2021 to 31 Oct 2022" is *s* = `2021-12`, *e* = `2022-10`.
This is the same as compounding the monthly returns from *s + 1* to *e*.

- *s* must be earlier than *e*, otherwise `ValueError`.
- If either month is outside the series, the period is **not covered** and a
  `CoverageError` is raised. A partly covered period is never shortened to fit.

### 1.4 Annualising

A total return *R* over *k* months is expressed per year as

    A = (1 + R) ^ (12 / k) − 1

- **Periods shorter than 12 months are never annualised** (`ValueError`). Scaling up a
  short period overstates what it means; performance-reporting standards forbid it.
- *R* must be greater than −100% (`ValueError` otherwise).

Example: +21% over 24 months is +10% a year, because 1.1 × 1.1 = 1.21.

### 1.5 Common window

Two series are compared only over the months they both cover. The common window runs
from the later of the two first months to the earlier of the two last months. Both
series are cut to that window, keeping their labels, and returned in the order given.
If the two series share fewer than 2 months (so no common return exists), a
`CoverageError` is raised.

## 2. Currency

Applies to assets priced in US dollars (the US stocks and bitcoin). Assets priced in
pounds are not converted and have no currency split.

### 2.1 The exchange rate

The GBP/USD series is the number of **US dollars per one pound**, at month-end, matched
by calendar month (section 1.1). It is labelled `basis` = `fx_rate`, `currency` = `USD`.
A higher number means a stronger pound.

### 2.2 Converting to pounds

    V_GBP(m) = V_USD(m) / rate(m)

- The asset must be labelled `USD` and must not itself be an exchange rate; the rate
  series must be labelled `fx_rate` and `USD`. Anything else is a `SeriesError`.
- The converted series covers only the months both series cover (section 1.5), so a
  US asset's history in pounds starts when the exchange-rate history starts. If they share
  fewer than 2 months, `CoverageError`.
- The converted series keeps the asset's name and basis and is labelled `GBP`.

### 2.3 Splitting a pound return into its two parts

For a period from month-end *s* to month-end *e* (section 1.3):

    local return     R_L = V_USD(e) / V_USD(s) − 1           (what the asset did in dollars)
    currency return  R_C = rate(s) / rate(e) − 1             (what the dollar did against the pound)
    pound return     R_G = V_GBP(e) / V_GBP(s) − 1           (what a UK investor experienced)

and these **compound**, they do not add:

    1 + R_G = (1 + R_L) × (1 + R_C)

- The currency return uses rate(s) / rate(e), not the other way round: when the pound
  falls, the dollar a UK investor holds is worth more pounds.
- A fall in the pound is not the same size as the dollar's rise. The pound falling from
  1.25 to 1.00 dollars is −20% for the pound but +25% for the dollar, and +25% is what a UK
  holder of dollar assets gains.
- Both *s* and *e* must be covered by the asset and the rate, otherwise `CoverageError`.
  *s* must be earlier than *e*, otherwise `ValueError`.
- **For the words layer:** because the parts compound, R_L + R_C is not R_G. Text must
  never say the two parts "add up to" the pound return.

### 2.4 What this cannot separate

Funds priced in pounds that hold dollar assets without hedging (the tracker, the gold
fund) carry a currency effect inside their pound price. With a single pound price, that
effect cannot be separated from the fund's own return, so no split is shown for them.

## 3. Volatility and largest fall

Both apply to a single series of values (`total_return` or `price`). An exchange-rate
series is rejected with `SeriesError`. Both work on whatever months the series covers;
to compare two assets, cut them to their common window first (section 1.5).

### 3.1 Volatility ("how bumpy is the ride?")

    volatility = sample standard deviation of the monthly returns × √12

- Monthly returns as in section 1.2. The sample standard deviation divides by *n − 1*,
  where *n* is the number of returns. At least 2 returns are needed (3 values), otherwise
  `CoverageError`.
- √12 turns monthly variability into a yearly figure. This is the standard convention;
  it assumes months are independent, which is an approximation.
- Volatility measures bumpiness, not direction. A series that rises by exactly 1% every
  month has zero volatility.

### 3.2 Largest fall ("what's the worst it's been?")

Measured on month-end values, and labelled "measured at month-end": a fall that
recovered within a month does not appear.

- **High so far.** For each month, the highest value up to and including that month.
  The first month counts as a high, so a fall that began before the series starts is
  measured only from the first month (bitcoin's data starts partway down from its
  2013 peak).
- **Drawdown** in month *m* = V(m) / high so far(m) − 1 (zero or negative).
- **Largest fall** = the most negative drawdown. If two months tie, the **earliest** is
  the trough.
- **Peak** = the last month, at or before the trough, whose value equals the high so far
  at the trough. (With 100, 120, 120, 60 the peak is the second 120: the fall starts
  from the last time the investor was at the high.)
- **Recovery** = the first month after the trough whose value is **at or above** the
  peak value. If there is none, the fall is **not recovered** by the last month.
- **Months:** peak to trough, trough to recovery, and underwater = peak to recovery. Each
  is the number of month-ends elapsed, so underwater = peak to trough + trough to
  recovery. If not recovered, underwater runs from the peak to the last month, and trough
  to recovery is empty.
- **In pounds:** £10,000 invested **at the peak** would have been worth
  £10,000 × (1 + largest fall) at the trough. Both that value and the amount lost are
  reported as positive numbers. The £ figure applies only to money invested at the high,
  and text must say so.
- **Drawdown at the end** = V(last month) / highest value in the whole series − 1. If the
  fall is not recovered, this is how far below its high the asset still was at the end
  ("not recovered by May 2020, still 25% below its high"). Never phrased as a forecast.
- **No fall.** If no month is below the high so far, the largest fall is 0, and the peak,
  trough, recovery and month counts are empty.

## 4. Stress windows and holding periods

Both apply to a single series of values (`total_return` or `price`); an exchange-rate
series is rejected with `SeriesError`. Both report **total returns over fixed periods**
(section 1.3), so a pence-quoted series gives the same answers as one in pounds.

### 4.1 Stress windows ("what happened when markets panicked?")

Three fixed windows, each measured from the month-end before its first month:

| Window | Start month-end | End month-end |
|---|---|---|
| `gfc` (global financial crisis) | 2007-09 | 2009-03 |
| `covid` (Covid crash) | 2020-01 | 2020-03 |
| `rate_shock` (2022 rate shock) | 2021-12 | 2022-10 |

- The window's return is V(end) / V(start) − 1.
- A window is **covered** only if the series has both its start and end month. A partly
  covered window is not covered, and is never shortened to fit.
- Because the dates are fixed, the asset and the tracker are always compared over
  identical months.
- A window's return is **not** its largest fall: an asset can fall further inside the
  window and partly recover before it ends. Text must say "over the period", never
  "fell by".
- No window is annualised (section 1.4).

### 4.2 Holding periods ("what did holding it for 1, 3 or 5 years look like?")

For a horizon of *h* months (12, 36 or 60), a **holding period** starts at any month-end
*i* and ends at month-end *i + h*. Its return is V(i + h) / V(i) − 1.

- **How many.** A series of *N* month-end values spans *N − 1* months and has
  **N − h** holding periods of length *h* (fence posts, not panels: 120 month-ends give
  108 twelve-month periods). If there are none, `CoverageError`.
- **They overlap.** Consecutive periods share all but one month, so they are not
  independent observations. The number of **non-overlapping** periods is
  (N − 1) ÷ h, rounded down (120 month-ends give 9 twelve-month periods). It is
  reported so the claims layer can apply the minimum-history rule once it is confirmed.
- *h* must be a whole number of years (12, 24, 36, ...), otherwise `ValueError`.
- **Worst, median, best** of the period returns, with the start and end month of the
  worst and best. If two periods tie, the **earliest** start is used. The median of an
  even number of periods is the average of the two middle values.
- **Lost money** means a return below zero. A period that ends exactly where it started
  did not lose money. Reported as a count and as a share of all periods.
- **Per year.** Each period's return is also annualised (section 1.4). The worst and best
  per-year figures are those of the worst and best periods. The median per-year figure is
  the median of all the per-year figures. Whether the site shows totals or per-year
  figures is decided in the claims layer.
- **Date range:** the first start month and the last end month.
- The historical worst is not the worst possible result. Text must say so.

## 5. Correlation and the 90/10 comparison

Both compare an asset with the tracker. The two series must have the **same currency**
and the **same basis**, and neither may be an exchange rate; anything else is a
`SeriesError`. Both are cut to their common window first (section 1.5), so they always
cover identical months.

### 5.1 Correlation ("does it move with the tracker?")

The Pearson correlation of the two series' monthly returns (section 1.2):

    correlation = Σ (a − mean a)(t − mean t) / √( Σ (a − mean a)² × Σ (t − mean t)² )

- It runs from −1 (always moving in opposite directions relative to their averages) to
  +1 (always moving together). It measures how consistently the monthly moves line up,
  **not their size**, and it is an average over all months, calm and stressed.
- At least 3 common monthly returns are needed, otherwise `CoverageError`. If either
  series has no variation at all, correlation is undefined: `SeriesError`.
- **Rolling correlation.** The same calculation over every run of *w* consecutive
  common monthly returns (the site uses *w* = 36). With *n* common returns there are
  *n − w + 1* runs. Reported: the number of runs, the lowest and highest values, and the
  month each of those runs ends. On a tie, the earliest run. *w* must be at least 3
  (`ValueError`); fewer than *w* common returns is `CoverageError`.
- **For the words layer:** a low or negative correlation is not a claim that the asset
  protects a portfolio. What the mix actually did is shown by section 5.2, not inferred
  from correlation.

### 5.2 The 90/10 comparison ("what does it do next to a tracker?")

An illustration over the common window: 100% tracker, against 90% tracker and 10% the
asset.

- **Start.** At the first month of the common window, the mix is 90% tracker and 10%
  asset.
- **Each month,** each part grows or shrinks by its own monthly return, so the weights
  drift.
- **Rebalancing:** at the end of **every December**, after that month's returns, the
  mix is reset to 90/10. A December that is the first month needs no reset. Before
  fees, with no trading costs and no tax.
- The asset's share is a parameter (the site uses 10%); it must be from 0 to 1
  (`ValueError`). With 0%, the mix is exactly the tracker.
- **Reported for both** the tracker and the mix, over the same months: total return,
  per-year return (section 1.4; empty if the window is shorter than 12 months),
  volatility (section 3.1) and the largest fall (section 3.2). Also the window's first
  and last month, the number of months, the asset's share and the rebalancing rule.
- The mix's month-by-month values are a rebased growth line. They are used inside the
  calculation only and are **never** returned or published (`DATA-RIGHTS.md`).
- Labelled illustrative, not recommended. For large caps already inside the tracker,
  text must say the 10% adds to something already held.

## 6. Engine output

One function, `analyse(asset, tracker, fx)`, produces everything the cards need. Nothing
else leaves the engine.

### 6.1 Inputs

- **Tracker:** labelled `GBP` and `total_return`, otherwise `SeriesError`.
- **Asset:** `total_return` only. A price-only series is refused (`SeriesError`), not
  labelled; everything in the v1 universe has total-return data.
  - Priced in `USD`: a GBP/USD series (section 2.1) must be given, and the asset is
    converted to pounds (section 2.2) before anything is measured. Missing `fx` is a
    `ValueError`.
  - Priced in `GBP`: `fx` must not be given (`ValueError`), so a rate is never silently
    ignored.
  - Any other currency: `SeriesError`.

### 6.2 What is measured

A **profile** of a series is: its first and last month and number of months, total
return (section 1.3) and per-year return (section 1.4, empty under 12 months),
volatility (3.1), largest fall (3.2), the three stress windows (4.1) and the 1-, 3- and
5-year holding periods (4.2).

- **Own:** the asset's profile over its full history in pounds.
- **Side by side:** the asset's and the tracker's profiles over their common months
  (1.5), plus correlation (5.1), the 36-month rolling correlation range (5.1) and the
  90/10 comparison with a 10% share (5.2).
- **Currency** (dollar assets only; empty for pound assets): the split (2.3) over the
  full history in pounds, and for each stress window.
- **Not covered is not an error.** Any part whose history is too short (a
  `CoverageError`) is reported as empty and the rest is still produced. Any other error
  stops the analysis.

### 6.3 What may leave

- Every output carries a **method version** (currently `1.0`), raised whenever this
  document changes a calculation.
- The output has a fixed shape. Every value is a single number (finite), text,
  true/false or empty. The **only** list allowed is the three stress windows, each a
  set of named values. Nothing shaped like a series can leave. The engine checks its own
  output against these rules before returning it and refuses (`OutputError`) if they are
  broken.
- Numbers are never rounded (general rules).

## 7. From provider rows to month-end values

The engine starts from month-end values (section 1.1). This section fixes how the data
pipeline picks them from what a provider returns. It is pure calculation, in
`pipeline/monthly.py`: no network, no files, no printing. Fetching happens elsewhere, and
raw rows are held in memory only (`DATA-RIGHTS.md`).

### 7.1 Provider rows

A provider's response is turned into a list of rows, each a (date, value) pair, in
whatever order the provider sent them. Alpha Vantage sends newest first.

- **Date.** Text that begins with a real calendar date written `YYYY-MM-DD`. It is either
  exactly that, or that followed by `T` and a time (`2020-01-31T00:00:00.000Z`). The date
  is taken as written: the time and any time zone are ignored, never converted. Crypto
  rows are labelled by their UTC day, which is what is written.
- **Value.** A number, or text holding a number (Alpha Vantage sends `"105.2500"`).
  True/false, empty text, nothing, and text that isn't a number are not values. A value
  must be finite.
- Tiingo is fetched daily and Alpha Vantage monthly. The same rule (7.3) picks the
  month-end from both, so one rule decides every month-end value.

### 7.2 The as-of month

Every run has one **as-of month**: the last month included for every instrument, shown
on the site as "data as of" that month's end.

- By default it is the **last complete calendar month before the run date**: the month
  before the run date's month. A run on 28 Sept 2026 gives `2026-08`. A run on 31 March
  gives February, because March's closing values may not be in until the month has
  ended.
- Rows after the as-of month (the unfinished current month) are dropped before anything
  in them is read.
- Every instrument must reach the as-of month, or a `CoverageError` is raised. No
  instrument is published with an earlier as-of month.

### 7.3 Picking the month-end value

For each calendar month from the start month (7.4) to the as-of month:

- The **month-end row** is the row with the **latest date** in that month, not the last
  row in the list.
- **Stale check.** The month-end row's date must fall in the **last 7 calendar days** of
  its month: from the 25th of a 31-day month, the 24th of a 30-day month, the 22nd of a
  28-day February, the 23rd of a 29-day February. Otherwise the run fails, naming the
  month and the date. Without this, a provider that hasn't yet posted the true last
  close, or a month missing its last days, would pass silently as a month-end value.
  Weekends, Good Friday and Christmas never move the last trading day earlier than this.
- **Only the month-end row's value is read.** Values on other days, and every row before
  the start month or after the as-of month, are neither used nor checked. Every row's
  date is checked, because the date decides where the row belongs.
- The result is a list of (month, value) pairs in ascending month order, one per month
  that has rows. It becomes a `MonthlySeries` (section 1.1), which rejects gaps, zeros
  and negative values. Those rules are the engine's and are not repeated here.

### 7.4 Start month

An instrument may have a start month, for history that is deliberately excluded. Months
before it are dropped unread (apart from their dates). If the start month has no rows,
a `CoverageError` is raised: the start is never moved to the first month that does have
data. With no start month, the series starts at the earliest month in the rows.

### 7.5 Errors

Checks run in this order, and the first problem stops the run:

1. **Arguments** (`ValueError`): the as-of month and any start month must be `YYYY-MM`
   with a month from 01 to 12, and the start must be earlier than the as-of month.
2. **Each row, in the order given** (`ProviderDataError`, naming the row number counted
   from 1, or the repeated date): it is a date and a value; the date is valid; the date
   has not appeared before. Two rows on the same date are a duplicate even if one
   carries a time.
3. **Coverage** (`CoverageError`, naming the month): the as-of month has rows, then the
   start month has rows.
4. **Each kept month, in ascending order** (`ProviderDataError`, naming the month): the
   stale check, then the value.

Messages name the row number, date or month and the problem, never a value: a value is
raw provider data.
