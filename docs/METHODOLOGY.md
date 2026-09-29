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
| 8. Instruments and published files | Pipeline 2 | `publish.json` | Written |
| 9. Fetching provider data | Pipeline 3a | `providers.json` | Written |
| 10. Running the pipeline | Pipeline 3b | `runner.json` | Written |
| 11. Claims and card text (cards 1 to 3) | Words 1 | `cards.json` | Written |

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
  is taken as written: the time and any time zone are ignored, never converted. For
  crypto, Tiingo's documentation does not say whether a daily bar is labelled by the day
  it starts or ends; this is checked in the first live run, and the finding recorded here.
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

## 8. Instruments and published files

In `pipeline/publish.py`. Pure, like section 7: no network, no files, no printing. The
runner (a later task) reads the instrument list, fetches, calls `analyse()`, and hands
the result here; this section decides what one published file contains and checks it.

### 8.1 The instrument list (`pipeline/instruments.json`)

Hand-written facts, taken from each issuer's own pages (and a broker page for how the
London line is quoted), checked by Avi against the links, committed by Avi. Codex never
edits it. `check_registry` refuses the whole list (`RegistryError`) if any rule below is
broken. It runs before any data is fetched.

- **Top level:** exactly `about` (text), `facts_checked` (a `YYYY-MM-DD` date),
  `providers`, `fx`, `instruments`.
- **Providers:** at least one. Each id (see ids below) maps to exactly `name` (text) and
  `url`.
- **Every URL** (provider and identity sources) starts `https://`, has something after it,
  and contains no `?`, no `#` and no spaces. A query string could carry an API key into a
  public file.
- **fx:** exactly `label` (text) and `data`. Its data has kind `fx`, currency `USD`, basis
  `fx_rate` (section 2.1).
- **Instruments:** at least one. Each has exactly `id`, `role`, `label`, `identity`,
  `data`.
  - `id`: 2 to 20 characters, lower-case letters and digits, starting with a letter,
    unique. It becomes a file name, so nothing else is allowed.
  - `role`: `benchmark` or `asset`. Exactly one benchmark, and it trades in `GBP`
    (section 6.1). The benchmark has no page of its own.
  - `label`: the short display name (text).
- **Identity:** exactly these keys.

  | Key | Rule |
  |---|---|
  | `name`, `ticker` | Text, not empty. |
  | `type` | `etf`, `etc`, `share` or `cryptocurrency`. |
  | `isin` | 2 capital letters, 9 capital letters or digits, 1 digit. Null for a cryptocurrency, and only then. |
  | `exchange` | Text. Null for a cryptocurrency (its price comes from a feed across many exchanges), and only then. |
  | `share_class` | Text for an ETF. Null for a cryptocurrency. Either for a share or an ETC. |
  | `trading_currency` | `GBP` or `USD`. |
  | `quote_unit` | `pence` or `pounds` for GBP; `dollars` for USD. |
  | `income` | ETF: `accumulating` or `distributing`. ETC: `none`. Share: `dividends` or `none`. Cryptocurrency: `none`. |
  | `currency_hedged` | True or false (an actual true/false, not 0 or 1) for an ETF or ETC. Null for a share or cryptocurrency. |
  | `sources` | A list of at least one URL. |

- **Data** (for fetching): exactly `provider` (one of the providers), `kind`, `symbol`
  and `field` (text), `currency`, `basis`, `start`.
  - `kind`: `crypto` for a cryptocurrency, `equity` for everything else. (`fx` is for the
    exchange rate only.)
  - `currency` equals the identity's `trading_currency`: it is the engine label, so a
    pound fund labelled USD would be divided by the exchange rate.
  - `basis` is `total_return`. Instruments that pay no income (the gold ETC, bitcoin) are
    total return by definition: their price is their total return.
  - `start`: null, or a `YYYY-MM` month (section 7.4).
- **Messages** name the instrument by its id whenever the id itself is valid (otherwise
  by position, counted from 1), or `fx`, or the provider id, plus the field. They never
  repeat a URL.

### 8.2 One published file (`build_document`)

`build_document(registry, instrument_id, results, as_of_month, generated_on)`:

1. Checks the instrument list (8.1).
2. Checks its arguments (`ValueError`): the instrument is an **asset** in the list (the
   benchmark gets no file); `as_of_month` is a valid `YYYY-MM`; `generated_on` is a date
   (not a date-and-time, not text) in a month **after** the as-of month, because data as
   of a month can't be complete before that month has ended (section 7.2).
3. Builds the document:

| Key | Contents |
|---|---|
| `document_version` | `"1"`. |
| `instrument` | `id`, `label` and `identity` of the instrument, copied from the list. |
| `benchmark` | The same three for the benchmark. |
| `data_as_of` | The as-of month, `YYYY-MM`. The site shows it as "data to the end of [month]". |
| `generated_on` | `YYYY-MM-DD`. |
| `sources` | Who supplied what (below). |
| `results` | The `analyse()` output, unchanged. |

- **Sources.** The data used for this file, in order: the instrument's, the benchmark's,
  then the exchange rate's (only for a `USD` instrument). Each provider appears once, at
  its first use, as `provider` (its name), `url`, and `used_for`: the labels it supplied,
  in that order.
- **Copies.** Everything taken from the list is a full copy, all the way down. Changing
  the list after a document is built must not change the document.
4. Checks the finished document (8.3) before returning it.

### 8.3 Checking a published file (`check_document`)

`check_document(document, registry)` is run by `build_document`, and again by the runner
on the file as read back from disk. It raises `PublishError`, naming the part that
failed and never repeating a URL or a value, at the first of these problems, in order:

1. The top-level keys are not exactly the seven in 8.2.
2. `document_version` is not `"1"`.
3. `instrument` is not an asset in the list, or is not exactly its copy.
4. `benchmark` is not exactly the list's benchmark.
5. `data_as_of` is not a valid `YYYY-MM`.
6. `generated_on` is not a valid `YYYY-MM-DD`, or its month is not after `data_as_of`.
7. `sources` is not exactly what 8.2 builds for this instrument.
8. The results:
   - the engine's own output rule (section 6.3) is applied first; its `OutputError` is
     passed on unchanged, never wrapped;
   - the keys are exactly `method_version`, `asset_currency`, `own`, `side_by_side`,
     `currency`;
   - `method_version` is the engine's current one;
   - `asset_currency` is the instrument's data currency (catches the wrong asset's
     results);
   - `own` is present and ends at `data_as_of`; if the instrument has a start month,
     `own` starts there;
   - `side_by_side` is present, and its `asset` and `tracker` both end at `data_as_of`;
   - `currency` is present for a `USD` instrument and empty for a `GBP` one.

Every instrument reaching the same as-of month, and carrying results from the current
method, is what lets one "data as of" date and one method version stand for the whole
site.

## 9. Fetching provider data

### 9.1 Where the code lives

- `pipeline/providers.py` is pure: it builds requests, reads responses and runs the fetch
  loop, with the connection and the pause passed in. No network, files or printing.
- `pipeline/network.py` is the **only** module that opens a connection. Codex writes it
  but never calls it for real; tests replace its `urlopen`. Avi runs the live fetch.

### 9.2 Keys and symbols

- A key must be letters and digits only, and not empty (`ValueError`, never showing the
  key). That keeps it from breaking into a URL.
- An equity or crypto symbol is letters, digits and dots. An exchange-rate symbol is
  three capitals, a slash, three capitals (`GBP/USD`). Anything else is a `ValueError`.
- **Tiingo** takes the key in the `Authorization` header (`Token <key>`), with
  `Content-Type: application/json`. **Alpha Vantage** takes it in the URL, as the last
  parameter. Because of that, **no URL is ever printed, logged or put in an error
  message.**

### 9.3 Requests

Exact URLs, parameters in the order written. Every request is built, and every argument
checked, before anything is requested.

| Provider, kind | Requests |
|---|---|
| Tiingo, equity | One: `https://api.tiingo.com/tiingo/daily/<symbol>/prices?startDate=1990-01-01`. Daily, full history (section 7 picks the month-ends). |
| Tiingo, crypto | One per calendar year, from the start month's year to the as-of month's year: `https://api.tiingo.com/tiingo/crypto/prices?tickers=<symbol>&startDate=<Y>-01-01&endDate=<Y>-12-31&resampleFreq=1day`. The endpoint caps the rows one request returns (found in the 28 Sept data check). A crypto instrument must have a start month, not after the as-of month. |
| Alpha Vantage, equity | One: `https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED&symbol=<symbol>&apikey=<key>`. The documentation marks this premium; the free tier served it in the 28 Sept data check. If that changes, the run fails with Alpha Vantage's message. It **never** falls back to `TIME_SERIES_MONTHLY`, which is price only. Near the daily limit, Alpha Vantage has answered `Invalid API call` before its rate-limit message (29 Sept); the same request worked on a fresh allowance. |
| Alpha Vantage, fx | One: `https://www.alphavantage.co/query?function=FX_MONTHLY&from_symbol=GBP&to_symbol=USD&apikey=<key>`. |

Any other provider and kind is a `ValueError`.

### 9.4 Reading a response

Each response becomes rows of [date, value] for section 7, in the order given. The value
is always the instrument's named `field`. If it is missing, the value is empty: **never
another field in its place** (close for adjusted close would silently turn a
total-return series into price only). Section 7 then fails closed if that row is a
month-end.

- **Tiingo, equity:** a list of objects; date from `date`. An object instead of a list
  is a Tiingo message: `ProviderError` with its `detail` text, cleaned (9.5). Anything
  else is a `ProviderError`.
- **Tiingo, crypto:** a list of at most one object. An empty list means no data that
  year: no rows, not an error. The object's `ticker`, if present, must equal the symbol
  (otherwise it is another instrument's prices). Rows come from its `priceData` list.
- **Alpha Vantage:** an object. If it has `Information`, `Note` or `Error Message`, that
  is a `ProviderError` carrying the text, cleaned. Otherwise, apart from `Meta Data`, it
  must have **exactly one** key, whose value is an object of date to entry. The series
  key's name is not relied on (the documentation and live responses name it
  differently; live responses on 29 Sept used `Monthly Adjusted Time Series`); zero or
  several candidates is a `ProviderError`. An entry that isn't an
  object gives an empty value.

### 9.5 Cleaning provider text

Text from a provider goes into an error message only after, in this order: the key is
replaced by `[key]`; anything after `apikey=` up to the next `&` or space is replaced by
`[key]`; runs of whitespace become one space; any web address (starting with a scheme
such as `https://`, or with `www.`) becomes `[url]`; the result is cut to 200
characters. Messages never contain a URL, a response body or a value. (Alpha Vantage's
rate-limit message writes the caller's key into its text; see `VERIFICATION.md`.)

### 9.6 The fetch loop

`fetch_rows(data, key, as_of_month, http_get, wait)` builds all the requests (9.3), then
for each in order: pauses, requests, reads (9.4), and adds the rows. The pause comes
**before every request**: 1 second for Tiingo, 13 seconds for Alpha Vantage (its free
tier limits requests per minute). A `ProviderError` from requesting or reading is raised
again as `ProviderError("<provider> <symbol>: <message>")`, with the message cleaned
again, and nothing further is requested.

### 9.7 The connection

`http_get_json(url, headers)` makes one GET with the headers and a 30-second timeout,
and returns the parsed JSON. Certificate checking is Python's default and is **never**
switched off. Errors are `ProviderError`, never showing the URL:

| Problem | Message |
|---|---|
| An HTTP error status | `HTTP <code>` |
| A timeout (on Python 3.9, `socket.timeout` is separate from `TimeoutError`; both count) | `timed out` |
| Any other connection failure | `connection problem (<error type>)` |
| A body that isn't JSON | `response was not JSON` (the body is never shown: it may hold prices) |

## 10. Running the pipeline

### 10.1 Where the code lives

- `pipeline/runner.py` is **the writer**: it writes files in the output folder and
  nowhere else. No network, no environment variables, no printing. The fetch is passed
  in.
- `scripts/build_data.py` is **the command Avi runs**. It reads the keys from the
  environment, prints a summary, and is the only place the real fetch (section 9, with
  `pipeline/network.py` and real pauses) is wired in. Its `main()` has no default fetch:
  only the script's own entry point passes the real one, so a test that forgets its fake
  fails instead of reaching the network.

### 10.2 `run(registry, fetch, today, out_dir)`

`fetch(data, as_of_month)` returns the rows for one data entry. In order:

1. `today` must be a date, not a date-and-time (`ValueError`).
2. **Instrument list:** `check_registry` (section 8.1).
3. **As-of month:** `last_complete_month(today)` (section 7.2).
4. **Output folder**, before anything is fetched. It must exist (`run` never creates it).
   Apart from names starting with `.` (macOS writes `.DS_Store`), which are left alone,
   it may hold only `<id>.json` for assets in the list. Anything else (a file from a
   removed instrument, the benchmark, a leftover `.tmp`, a subfolder) stops the run,
   naming the first such name in alphabetical order. A stale file could otherwise go on
   being published.
5. **Series**, in this order: the exchange rate, the benchmark, then each asset in list
   order. For each: `fetch`, then `build_monthly_series(label, currency, basis, rows,
   as_of, start)` from its data entry (section 7). For each asset, straight after its
   series: `analyse(asset, tracker, fx)`, with `fx` only for a `USD` asset (section 6),
   then `build_document(registry, id, results, as_of, today)` (section 8). The first
   failure stops the run: nothing more is fetched.
6. **Write, all or nothing**, only once every document is built. Each document becomes
   `json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"` in UTF-8,
   written to `<id>.json.tmp`. Every temporary file is then read back, parsed and checked
   again with `check_document` (section 8.3). Only then is each renamed to `<id>.json`,
   replacing last run's. If anything fails before the first rename, every temporary file
   created is removed and the folder is exactly as it was. (A failure during the renames
   themselves, a disk or permissions error, is the one case that can leave a mix;
   `git status --short` shows it.)
7. **Return a summary:** `{"as_of": ..., "series": [...], "written": [...]}`. Each series
   entry is `{"id", "first", "last", "month_ends"}`, in fetch order, with the exchange
   rate's id written as `fx`. `month_ends` counts month-end values (4 for May to August),
   not months elapsed (3). `written` lists the file names in asset order.

**Errors** are a `RunError` whose message names who and which step:
`<who>: <step>: <ErrorType>: <message>`. Who is `registry`, `fx` or an instrument id;
step is `check`, `fetch`, `series`, `analyse`, `document` or `write`. The message is
included only for the pipeline's own error types (`RegistryError`, `ProviderError`,
`ProviderDataError`, `CoverageError`, `SeriesError`, `PublishError`, `OutputError`),
whose messages are value-free by design. Any other type is named alone (`gbf: fetch:
RuntimeError`): its message could hold anything, including a value or a key.
Output-folder problems are `output folder: does not exist` or `output folder: unexpected
<name>`.

### 10.3 The command: `python3 scripts/build_data.py [--list]`

`main(argv, environ, today, out, root, make_fetch)` returns the exit code and writes
lines to `out`. It never prints a traceback, a key, a URL or a value. The instrument
list is `root/pipeline/instruments.json`; the output folder is `root/data/derived`.

- **Arguments:** none, or `--list`. Anything else prints
  `Usage: python3 scripts/build_data.py [--list]` and returns 2.
- **Both modes first** load the instrument list (`FAILED: registry: load: <ErrorType>`)
  and check it (`FAILED: registry: check: RegistryError: <message>`), each followed by
  `Nothing was fetched or written.` and exit code 1.
- **`--list`** needs no keys and makes no requests. It prints
  `Plan: data as of <as_of> (run on <today>).`, then one line per series in run order,
  `<id>: <provider> <kind> <symbol>, <n> request(s)` (from `build_requests`, section 9.3,
  with a placeholder key), then `<total> request(s), <seconds> seconds of pauses. No
  requests made.` and returns 0. The pauses are the section 9.6 pause for each request.
- **A full run:**
  1. **Keys.** For each provider used by the exchange rate or any instrument, in the order
     the providers are listed, the key is the environment variable `<PROVIDER ID IN
     CAPITALS>_API_KEY` (`TIINGO_API_KEY`, `ALPHAVANTAGE_API_KEY`). Each one missing or
     empty prints `FAILED: <NAME> is not set in this terminal.`; if any is missing, then
     `Nothing was fetched or written.` and exit code 1.
  2. Create `data/derived` if it doesn't exist.
  3. `fetch = make_fetch(keys)`, where keys maps provider id to key.
  4. `run(...)`. On success it prints `Data as of <as_of> (run on <today>).`, then one line
     per series, `<id>: <first> to <last> (<n> month-ends)`, then `Wrote <n> files to
     data/derived. No prices were printed or saved.`, and returns 0.
  5. On a `RunError`: `FAILED: <message>`. On anything else: `FAILED: unexpected
     <ErrorType>.` Either way, then `Check git status --short before committing
     anything.` and exit code 1.

## 11. Claims and card text (cards 1 to 3)

In `words/cards.py`. Pure: it reads one published document (section 8) and returns the
text for cards 1 to 3 and the claims behind every number in it. No files, no network, no
printing. The site shows this text as it is; nothing is worded or rounded anywhere else.

### 11.1 Claims

Every number in a sentence is a **claim**:

| Field | Meaning |
|---|---|
| `id` | Unique on the page, e.g. `worst.fall`, `panic.covid.tracker`. |
| `series` | `asset` or `tracker`. |
| `instrument` | The asset's id, or the benchmark's id for a tracker claim. |
| `metric` | The engine field it comes from (`volatility`, `largest_fall`, `months_peak_to_trough`, `ten_thousand_at_trough`, `ten_thousand_lost`, `months_trough_to_recovery`, `months_underwater`, `drawdown_at_end`, `stress_window`). |
| `period_start`, `period_end` | The month-ends the number covers. |
| `unit` | `percent`, `gbp` or `months`. |
| `currency` | `GBP` for percent and £ claims; empty for months. |
| `value` | The number after its one rounding: percentage points as a float with one decimal place (signed), whole pounds as an integer, months as an integer. |
| `direction` | For returns and falls: `down`, `up`, or `flat` if the rounded value is zero. Empty for volatility, £ and months. |
| `display` | Exactly the text shown in the sentence: `72.5%`, `£2,750`, `14 months`. |
| `kind` | `observed` (history). Cards 1 to 3 have no illustrations. |

Each sentence lists the claim ids it uses, in the order they appear. Every claim's
`display` appears in its sentence. Fixed sentences have no claims.

### 11.2 Rounding and display, once

- **Percentages:** take the value as written (Python's `repr`, as a `Decimal`), multiply by
  100 exactly, and round to one decimal place, half-up (away from zero). Never multiply
  the float first: 0.0725 x 100 is 7.249999999999999 in floating point and would round to
  7.2, where the right answer is 7.3. A result of zero is `0.0`, never `-0.0`. The text is
  the size only, with a thousands comma (`41,992.8%`); direction is in the words.
- **Pounds:** nearest £10, half-up, written `£2,750`. The amount lost is £10,000 minus
  the rounded amount left, so the two always add up to £10,000.
- **Months:** whole numbers given as integers; `1 month`, otherwise `N months`.
- **Months of the year:** `Sep 2007`; a month-end is written `the end of Sep 2007`.
- True/false, text, empty and non-finite values are refused (`ValueError`).

### 11.3 Card 1: How bumpy is the ride?

1. `Its volatility was {own volatility} a year, measured on monthly returns in pounds
   from the end of {own start} to the end of {own end}.`
2. If the asset's own history starts earlier than the side-by-side window:
   `Over the same months as the tracker, from the end of {side-by-side start} to the end
   of {side-by-side end}, it was {asset volatility, side by side} against the tracker's
   {tracker volatility}.` Otherwise: `Over the same months, the tracker's was {tracker
   volatility}.`
3. `Volatility measures how widely returns swung around their average, up as well as
   down. It describes the past, not the future.`

### 11.4 Card 2: What's the worst it's been?

If the largest fall is zero, one sentence only: `Since the end of {own start}, it has not
been below a previous high at any month-end.` Otherwise:

1. `Since the end of {own start}, its largest fall, measured at month-end, was {fall}:
   from its high at the end of {peak} to its low at the end of {trough}, {months peak to
   trough} later.`
2. `£10,000 invested at that high would have been worth {£ left} at the low, {£ lost}
   less.`
3. If recovered: `It was back at that high by the end of {recovery}, {months trough to
   recovery} after the low and {months underwater} after the high.` If not: `It had not
   recovered by the end of {own end}: it was still {drawdown at end} below its high,
   {months underwater} after it.` Never "never recovered": the data says what had
   happened by one month, not what will.
4. `Falls are measured from one month-end to the next, so a fall that recovered within a
   month doesn't show. The £10,000 figure applies only to money invested at the high.`

### 11.5 Card 3: What happened when markets panicked?

For each window in order (global financial crisis, Covid crash, 2022 rate shock), with
its heading `{name} (end of {start} to end of {end})`:

- The asset, from its own history: `{heading}: down {x} over the period.` (or `up`, or
  `unchanged (0.0%)` when it rounds to zero), or, if not covered, `{heading}: not
  covered; its history in pounds starts at the end of {own start}.`
- The tracker, from the side-by-side window: `The tracker: down {x} over the same
  period.` (or `up`, or `unchanged (0.0%)`), or `The tracker: not covered.`
- Then, once: `Each figure compares the start and end of the period. Prices may have
  fallen further in between and partly recovered.`

Stress-window returns are never "fell by": the figure compares two month-ends, not the
lowest point in between.

### 11.6 What is read, and errors

`build_cards` reads only: the instrument's and benchmark's `id`; from `own`: `start`,
`end`, `volatility`, `largest_fall` and `stress_windows`; from `side_by_side`: the
asset's `start`, `end` and `volatility`, and the tracker's `start`, `end`, `volatility`
and `stress_windows`. Anything it needs that is missing or empty (a window marked covered
without a return, a fall without its £ figure, an unknown window name) is a `WordsError`
naming the field. A missing number is never shown as blank or zero.

The asset is always "it" and the benchmark "the tracker"; the page names both in full
once, outside the cards.
