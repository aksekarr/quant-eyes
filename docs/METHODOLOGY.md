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
| 5. Correlation and the 90/10 comparison | 5 | `portfolio.json` | To come |
| 6. Engine output | 6 | `output.json` | To come |

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
