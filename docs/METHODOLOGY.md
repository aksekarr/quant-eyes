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
| 12. Card text (cards 5 to 7) | Words 2 | `cards_567.json` | Written |
| 13. Page data | Words 3 | `page.json` | Written |
| 14. Writing the site's data | Site 1 | `build_pages.json` | Written |
| 15. The headline (15.1 to 15.4) | Words 4 | `headline.json`, `draft_headlines.json`, `build_pages.json` | Written |
| 16. The site pages | Site 2 | `site_render.json` | Written |
| 17. Writing the site's pages | Site 3 | `build_site.json` | Written |

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

## 12. Card text (cards 5 to 7)

In `words/cards_567.py`, with the same rules as section 11 and reusing its helpers
(rounding, month names, `WordsError`). `build_cards_567(document, facts)` takes one
published document and the asset's entry from `words/context.json`, and returns cards 5
to 7 and their claims. Card 4 (holding periods) is not in v1.

### 12.1 The facts file (`words/context.json`)

Hand-checked facts the text needs that are not in the price data, one entry per asset,
with its reason and sources. Codex never edits it. Each entry gives:

- `held_by_tracker`: the tracker (MSCI World) holds this asset. Microsoft, Apple, Nvidia
  and AstraZeneca (MSCI factsheets, 31 Aug 2026).
- `priced_in_pounds_holds_dollars`: priced in pounds but holding something priced in
  dollars, so it carries a currency effect that can't be separated (the physical gold ETC).

`build_cards_567` receives exactly those two true/false values. Missing keys, other keys,
anything but true or false, or `priced_in_pounds_holds_dollars` for an asset that has
currency results (a dollar asset), is a `WordsError`.

### 12.2 More display rules

- **Correlation:** the value as written (`repr`, as a `Decimal`), two decimal places,
  half-up; zero is `0.00`; a negative value keeps its sign, written with a true minus sign
  (U+2212): `−0.29`. Claims have unit `ratio`, no currency, no direction.
- **Signed percentages** (the 90/10 returns a year): as section 11.2, but a negative value
  is written with a true minus sign (`−2.1%`). Direction `up`, `down` or `flat`.
- **New claim fields:** series may also be `mix` (the 90/10 illustration, kind
  `illustration`) or `currency` (what the dollar did against the pound). Dollar returns
  have currency `USD`; the currency part has none.
- A 36-month run's claim period starts 36 months before the month it ends.

### 12.3 Card 5: What does it do next to the tracker?

(Not "a global tracker": the tracker is developed-world only.)

1. `Its correlation with the tracker was {correlation}, measured on monthly returns in
   pounds from the end of {side-by-side start} to the end of {side-by-side end}: 1 would
   mean always moving in step, 0 no pattern, and −1 always opposite.`
2. `Measured over each 36-month stretch, it ranged from {lowest} (the 36 months to the
   end of {lowest end}) to {highest} (the 36 months to the end of {highest end}).`
3. `Correlation says how consistently the monthly moves lined up, not how big they were.
   A low figure is not protection.`
4. `As an illustration, not a recommendation: from the end of {mix start} to the end of
   {mix end}, a mix of 90% in the tracker and 10% in this investment, reset to 90/10 at
   the end of every December, returned {mix a year} a year, against {tracker a year} a
   year for the tracker alone.`
5. `The mix's volatility was {mix volatility} against the tracker's {tracker volatility},
   and its largest fall at month-end was {mix fall} against {tracker fall}.`
6. `Before fees, trading costs and tax.`
7. Only if held by the tracker: `The tracker already holds these shares, so the 10% adds
   to a holding it already has.`

The words say 90/10 and every December, so an asset weight other than 0.1 or a
rebalancing rule other than `december` is a `WordsError`, never described wrongly.

### 12.4 Card 6: How much of it was the pound?

- **A dollar asset** (it has currency results):
  1. `From the end of {start} to the end of {end}: {up|down x|unchanged (0.0%)} in
     dollars, and the dollar {rose|fell y|was unchanged (0.0%)} against the pound, so in
     pounds it was {up|down z|unchanged (0.0%)}.`
  2. For each covered stress window, in order: `{window name}: {..} in dollars, the
     dollar {..}, so {..} in pounds.` Windows not covered are skipped (card 3 already
     says so).
  3. `The two parts multiply rather than add, so they never simply add up to the figure
     in pounds.`
- **Priced in pounds, holding dollars:** `It is priced in pounds, but what it holds is
  priced in dollars, so part of its return in pounds comes from the pound against the
  dollar. With only a price in pounds, that part can't be separated out.`
- **Otherwise:** `It is priced in pounds, so there is no separate currency effect to
  show.`

### 12.5 Card 7: What these numbers don't capture

One sentence for the instrument type, then one for all:

- share: `A single company's shares can fall a long way and stay down, and the company
  can fail.`
- etf: `A fund's value moves with what it holds: bond prices, for example, fall when
  interest rates rise. Its market price can differ slightly from the value of its
  holdings, and its running charges are already inside these figures.`
- etc: `This is an exchange-traded commodity: a security backed by metal held in a vault,
  not the metal itself. It pays no income, and you rely on the issuer and on the
  custodian holding the metal.`
- cryptocurrency: `It is not issued or backed by a government or a company, and it pays
  no income. Its price can move a long way in days, it trades around the clock, and
  holdings can be lost to theft or lost keys. Its history here starts at the end of {own
  start}, so it covers fewer market conditions than the others.`
- All: `These are past results in pounds, measured at month-ends, before platform fees,
  trading costs and tax. Past behaviour does not predict future results.`

### 12.6 What is read, and errors

`build_cards_567` reads only: the instrument's `id` and `identity.type`; the benchmark's
`id`; `own.start`; from `side_by_side`: the asset's `start` and `end`, `correlation`,
`rolling_correlation_36` (`lowest`, `lowest_end`, `highest`, `highest_end`) and
`blend_90_10` (`start`, `end`, `asset_weight`, `rebalance`, and for both `blend` and
`tracker`: `annualised_return`, `volatility`, `largest_fall.max_drawdown`); and
`currency` (`full_history` and `stress_windows`, each with `start`, `end`, `covered` for
windows, `local_return`, `currency_return`, `gbp_return`). Anything needed that is
missing or empty is a `WordsError` naming it.

## 13. Page data

In `words/page.py`. Pure, like sections 11 and 12, reusing their builders. It turns one
published document (section 8) into everything one asset page shows, and builds the
landing page's list. Nothing on the site is worded, rounded or computed anywhere else.

### 13.1 The facts file check (`check_context`)

`words/context.json` (section 12.1) is refused (`WordsError`, naming the instrument and
field, never repeating a URL) unless:

- its top-level keys are exactly `about` (text), `facts_checked` (a `YYYY-MM-DD` date),
  `sources` (at least one name mapped to a URL) and `instruments`;
- every URL follows the rule in section 8.1 (https, no query, no fragment, no spaces);
- `instruments` has exactly one entry per asset in the instrument list: none for the
  benchmark, none for anything else;
- each entry has exactly `held_by_tracker` and `priced_in_pounds_holds_dollars` (true or
  false, not 0 or 1) and `why` (text, not blank);
- `priced_in_pounds_holds_dollars` is true only for an asset that trades in `GBP`.

### 13.2 One page (`build_page`)

`build_page(document, facts)`, where `facts` is the asset's context entry without `why`:

| Key | Contents |
|---|---|
| `page_version` | `"1"`. |
| `instrument`, `benchmark` | Copied from the document. |
| `data_as_of` | The as-of month, `YYYY-MM`. |
| `data_as_of_text` | `Data to the end of {Mon YYYY}`, e.g. `Data to the end of Aug 2026`. Never "as of 31 Aug": the data is month-end values. |
| `generated_on` | From the document. |
| `method_version` | From the results. |
| `sources` | Copied from the document. |
| `cards` | Cards 1 to 3 (section 11) then 5 to 7 (section 12): `bumpy`, `worst`, `panic`, `next`, `pound`, `limits`. |
| `claims` | Section 11's claims, then section 12's. Claim ids must be unique. |
| `headline` | Empty (null). The page writer fills it with the asset's approved headline, if there is one (section 14.1 step 6, section 15.4). |

A missing `data_as_of`, `generated_on`, `sources` or `method_version` is a `WordsError`.

### 13.3 The landing list (`build_index`)

`build_index(registry, pages)` checks, in order: every page is for an asset in the list,
and no asset has two pages; every page has the same `data_as_of`, `generated_on` and
`method_version` (one date and one method version stand for the whole site); every asset
in the list has a page. Then it returns:

| Key | Contents |
|---|---|
| `index_version` | `"1"`. |
| `data_as_of`, `data_as_of_text`, `generated_on`, `method_version` | The shared values. |
| `benchmark` | Its `id`, `label`, and identity `name` and `ticker`, from the instrument list. |
| `assets` | For each asset, in the instrument list's order: `id`, `label`, and identity `name`, `ticker` and `type`. |

## 14. Writing the site's data

`scripts/build_pages.py` is the page writer and the command Avi runs after each data
refresh: `python3 scripts/build_pages.py`. It is offline: no network, no keys, no
environment variables and no clock. It reads committed files and writes only in
`site/data`. The same inputs always give byte-identical files, so a run with nothing new
shows no change in `git status`.

### 14.1 `write_pages(registry, context, documents, approvals, out_dir)`

`documents` maps each asset id to its published document (section 8), as read from
`data/derived/<id>.json`. In order:

1. **Instrument list:** `check_registry` (section 8.1).
2. **Facts file:** `check_context` (section 13.1).
3. **Output folder**, as in section 10.2 step 4. It must exist (`write_pages` never
   creates it). Apart from names starting with `.`, which are left alone, it may hold only
   the files `<id>.json` for assets in the list and `index.json` (a folder or link with
   one of those names is unexpected too). Anything else (a page for a removed instrument
   or for the benchmark, a leftover `.tmp`, a subfolder) stops the run, naming the first
   such name in alphabetical order. A removed instrument's page is deleted by hand
   (`git rm`), never silently.
4. **Documents:** every asset in the list has an entry, checked in list order; then there
   is no other entry (the first other name in alphabetical order is named).
5. **Pages**, for each asset in list order, finishing one asset before the next:
   `check_document(document, registry)` (section 8.3); the document's instrument must be
   that asset; then `build_page(document, facts)` (section 13.2), where `facts` is the
   asset's context entry without `why`; then the page's `guided` becomes
   `build_guided(page, facts)` (section 18). A `WordsError` from it is reported as
   `<id>: page: WordsError: <message>`, like `build_page`'s.
6. **Headlines** (section 15.4): `check_approvals(approvals, pages, registry)` (section
   15.2), with the pages in list order. Each page's `headline` becomes its asset's approved
   headline, or stays empty (null) if it has none.
7. **Index:** `build_index(registry, pages)` (section 13.3), with the pages in list order.
8. **Write, all or nothing**, as in section 10.2 step 6. Each page and the index becomes
   `json.dumps(value, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False) + "\n"`
   in UTF-8 (so `£` and `−` stay readable in `git diff`), written to `<id>.json.tmp` and
   `index.json.tmp`. Every temporary file is then read back and parsed, and must equal the
   value built: the pages in list order, then the index. Only then is each file renamed
   into place, the pages in list order and `index.json` last. If anything fails before
   the first rename, every temporary file created is removed and the folder is exactly as
   it was.
9. **Return** `{"data_as_of", "generated_on", "method_version", "headlines",
   "headlines_as_of", "written"}`: the index's shared values; the ids of the assets whose
   page has a headline, in list order; the approvals file's `data_as_of`; and the file
   names in the order they were renamed.

**Errors** are a `PageError` (defined in `scripts/build_pages.py`), in the form
`<who>: <step>: <ErrorType>: <message>`, as in section 10.2. The message is included only
for `RegistryError`, `PublishError` and `WordsError`, whose messages are value-free by
design; any other type is named alone (`usa: page: RuntimeError`).

| Step | Messages |
|---|---|
| 1 | `registry: check: RegistryError: <message>` |
| 2 | `context: check: WordsError: <message>` |
| 3 | `output folder: does not exist`, `output folder: unexpected <name>` |
| 4 | `<id>: document: missing`, `documents: unexpected <name>` |
| 5 | `<id>: check: PublishError: <message>`, `<id>: document: for <other id>`, `<id>: page: WordsError: <message>` |
| 6 | `headlines: check: WordsError: <message>` |
| 7 | `index: build: WordsError: <message>` |
| 8 | `<file>: write: <ErrorType>` for the file being written or read back (`usa.json`, `index.json`), with the message only for the three types above; `<file>: write: read back differently` |

### 14.2 The command: `python3 scripts/build_pages.py`

`main(argv, root, out)` returns the exit code and writes lines to `out`. It never prints a
traceback or a value.

- **Arguments:** none. Anything else prints `Usage: python3 scripts/build_pages.py` and
  returns 2.
- **Loading**, in this order. Each file is read as UTF-8 with `json.load`. Each failure
  prints its line, then `Nothing was written.`, and returns 1, before `site/data` is
  touched:
  1. `root/pipeline/instruments.json`: `FAILED: registry: load: <ErrorType>`. Then
     `check_registry`: `FAILED: registry: check: RegistryError: <message>` (another type
     is named alone).
  2. `root/words/context.json`: `FAILED: context: load: <ErrorType>`.
  3. `root/data/derived/<id>.json` for each asset, in list order:
     `FAILED: <id>: load: <ErrorType>`.
  4. `root/words/headlines.json` (section 15.4): `FAILED: headlines: load: <ErrorType>`.
- Create `root/site/data` if it doesn't exist (and `root/site`).
- `write_pages(registry, context, documents, approvals, root/site/data)`. On success it
  prints `Data as of <data_as_of>, generated on <generated_on>, method <method_version>.`,
  then one headlines line, then `Wrote <n> files to site/data.`, and returns 0. The
  headlines line is `Headlines: <k> of <n> pages have an approved headline.` when the
  approvals file is for the pages' month (`<n>` is the number of assets), and otherwise
  `Headlines: none, because words/headlines.json is for <its data_as_of>; draft and review
  headlines for <data_as_of>.`
- On a `PageError`: `FAILED: <message>`. On anything else: `FAILED: unexpected
  <ErrorType>.` Either way, then `Check git status --short before committing anything.`
  and exit code 1.

## 15. The headline

The one AI-written line on each asset page (`docs/BRIEF.md`, "Words"). Avi's decisions
(29 Sept): one neutral, past-tense sentence of at most 30 words, using one or two of the
asset's own figures; OpenAI `gpt-6.1-sol` drafts it; code checks it; Avi reviews every
headline by editing an approvals file; after a data refresh, last month's headlines are
dropped until he approves new ones. Nothing reaches a page any other way.

The checker and approvals (15.1, 15.2) are in `words/headline.py`, pure like sections 11 to
13; drafting (15.3) adds to it, plus a POST in `pipeline/network.py` and the command
`scripts/draft_headlines.py`. The page writer publishes approved headlines (15.4, which
amends section 14).

### 15.1 The checker: `check_headline(text, claim_ids, page, registry)`

Returns a list of problems, each `"<rule>: <detail>"` with a non-empty detail; an empty
list means the headline passes. `page` is a section 13 page (only its instrument's `id`
and its `claims` are read); `registry` has passed `check_registry`. It never raises for a
bad `text` or `claim_ids`: it reports them. The *cited claims* are the page's claims whose
ids are in `claim_ids`.

The rules, in this order. If **text** or **claims** fails, that is the only problem
returned.

1. **text**: a string, not empty, with no leading or trailing whitespace and no line
   break or tab.
2. **claims**: a list of 1 or 2 different ids, each the id of a claim on the page.
3. **citable**: every cited claim has series `asset` and kind `observed`, the asset's own
   history: not the tracker's figures, the 90/10 illustration or the currency part.
4. **one_sentence**: the text ends with `.`; before that, it has no `!`, `?` or `;`, and
   every other `.` has a digit on both sides (a decimal point).
5. **length**: at most 30 words, counting the pieces between whitespace.
6. **uncited_number** and 7. **display_missing**, the figures. The *allowed phrases* are,
   for each cited claim: its `display`; the start and end months of its period, written as
   `Mon YYYY` (`month_name`, section 11); `£10,000` if its id starts with
   `worst.ten_thousand`; `2022 rate shock` if its id contains `rate_shock`. A phrase
   *occurs* where it appears exactly (case-sensitive), with just before it the start of
   the text or a character that is not a letter, a digit or one of `. , £ $ € − - + /`,
   and just after it the end of the text or a character that is not a letter, a digit or
   `%`, and is not a `.` or `,` followed by a digit. Longer phrases are matched first, and
   an occurrence may not overlap one already matched. Matched text is *covered*.
   - **uncited_number**: a digit, or one of `% £ $ €`, outside covered text. So every
     number is a cited figure written exactly as its card shows it (value, unit and
     currency together, with no sign glued on: the words carry the direction), and every
     date is the start or end of a cited figure's period.
   - **display_missing**: a cited claim whose display does not occur. Citations are not
     padding.

Rules 8 to 12 look at the *words*: the runs of letters `a` to `z` (with apostrophes
inside, as in `won't`) in the text lower-cased, after covered text is blanked out and `’`
is replaced by `'`. A word ending in `'s` also counts without it. A phrase is two
consecutive words. Each rule fails if any word or phrase on its list is present.

8.  **advice**: buy, buys, buying, bought, sell, sells, selling, sold, should,
    attractive, cheap, cheaper, cheapest, safe, safer, safest, safety, guarantee,
    guaranteed, guarantees, recommend, recommends, recommended, recommendation,
    diversifier, diversify, diversifies, diversification, hedge, hedges, protect,
    protects, protected, protection; "limited to".
9.  **future**: will, won't, shall, expect, expects, expected, expecting, forecast,
    forecasts, predict, predicts, predicted, prediction, future, likely, could, may, might,
    outlook, poised, ahead, soon; "going to", "set to".
10. **number_word**: zero, one, two, three, four, five, six, seven, eight, nine, ten,
    eleven, twelve, thirteen, fourteen, fifteen, sixteen, seventeen, eighteen, nineteen,
    twenty, thirty, forty, fifty, sixty, seventy, eighty, ninety, hundred, thousand,
    million, billion, dozen, twice, thrice, double, doubled, doubling, triple, tripled,
    quadruple, half, halved, halving, quarter, third, percent; "per cent"; and any word of
    more than 4 letters ending in `fold`. A figure the model works out itself ("twice the
    tracker's") is not a claim.
11. **comparison**: than, versus, vs, compared, comparison, relative, outperform,
    outperformed, outperforming, underperform, underperformed, beat, beats, beating,
    tracker, benchmark, index. The headline is about the asset alone; comparisons stay in
    card 5, with their numbers.
12. **loaded**: only, just, merely, huge, massive, enormous, extreme, extremely, dramatic,
    dramatically, stunning, incredible, impressive, spectacular, terrible, disastrous,
    catastrophic, soared, soaring, plunged, plummeted, crashed, skyrocketed, rocketed,
    collapse, collapsed, never, largest, biggest, worst, deepest, steepest, sharpest,
    greatest, highest, lowest, record, ever; "all time". ("Never" is a claim about all time,
    and the data stops at a month-end: "never recovered" is exactly the slip rule 15 exists
    for. The superlatives were added on 30 Sept, after the first real drafts called six falls
    the "largest" with no window: a superlative ranks a fall against all of history, and the
    data starts at a fixed month. A headline dates a fall; it never ranks it.)
13. **other_instrument**: the label, identity name or identity ticker of any other
    instrument in the list, the benchmark included, appears in the text (case-insensitive,
    not inside a longer run of letters and digits).
14. **direction**: a cited claim with direction `down` needs one of these words: fall,
    falls, fell, fallen, falling, drop, drops, dropped, down, decline, declined, declines,
    lost, lose, loss, losses, below, lower. One with direction `up` needs one of: rise,
    rises, rose, risen, rising, gain, gains, gained, up, grew, grow, grown, growth,
    increase, increased, increases, higher, above.
15. **recovery**: whether the asset's largest fall recovered comes from the page's claims
    (all of them, not only the cited ones): *not recovered* if there is a
    `worst.below_high_at_end` claim, *recovered* if there is a `worst.months_to_recover`
    claim, and *no fall* otherwise. The recovery words are: recover, recovers, recovered,
    recovering, recovery, regain, regains, regained, regaining, back. A recovery word is
    *negated* if one of the two words just before it is `not` or ends in `n't`; for this
    rule each run of letters is one word (a possessive is not counted twice). For a fall
    that had not recovered, every recovery word must be negated ("had not recovered"); for
    one that recovered, none may be ("it recovered", never "it had not recovered"); with no
    fall, no recovery word may appear. Added on 29 Sept after a trial on the real pages
    passed "It fell 31.9% from May 2020 to Oct 2023 and took 75 months to get back to that
    high" for IGLT: both figures were real claims, and the sentence was false. IGLT had
    not recovered; 75 months was its time below the high so far.
16. **currency**: only for a page whose asset trades in `USD` (its identity
    `trading_currency` in the instrument list; section 8.1 allows only `GBP` and `USD`).
    Each cited claim with currency `GBP` needs the phrase "in pounds", and each with
    currency `USD` the phrase "in dollars": the two words, one after the other, among the
    words (as rules 8 to 12 read them). A claim with no currency (a count of months, a
    correlation) needs nothing. Added on 30 Sept, after the second drafts gave dollar
    assets' falls in pounds without saying so: in 2008 the pound's fall made falls in
    pounds far smaller than the same falls in dollars (Microsoft's card 6: down 35.8% in
    dollars, 8.3% in pounds, over the financial-crisis window), so a reader who remembers
    the dollar fall concludes the figure is wrong.

Within a rule, problems follow the order they are found. The word lists are part of the
method: changing one is a methodology change with its own golden cases.

What code cannot check: whether a correct figure is framed fairly. "It fell 35.5% before
recovering" and "it recovered after falling 35.5%" pass alike; so would a rise word used
somewhere else in the sentence. That is why every headline is reviewed by Avi before it is
published (15.2), and why the page records who drafted it and when it was reviewed.

### 15.2 Approved headlines: `words/headlines.json` and `check_approvals(approvals, pages, registry)`

`words/headlines.json` holds the headlines Avi has approved. He writes it from the drafts
(15.3) and commits it; nothing else edits it.

```json
{
  "data_as_of": "2026-08",
  "headlines": {
    "msft": {"text": "…", "claims": ["worst.fall"], "drafted_by": "gpt-6.1-sol", "reviewed_on": "2026-09-30"}
  }
}
```

`check_approvals(approvals, pages, registry)` returns `{asset id: headline}` for the
headlines that may be published, in the instrument list's order. Each headline is a copy
with exactly `text`, `claims`, `drafted_by` and `reviewed_on`. `pages` is the list of
section 13 pages being built. It raises `WordsError`, naming the field and the asset,
unless:

- the top-level keys are exactly `data_as_of` (a month, `YYYY-MM`) and `headlines` (a
  dictionary, which may be empty);
- every key of `headlines` is an asset in the list, not the benchmark;
- every entry has exactly `text`, `claims`, `drafted_by` (text, not blank) and
  `reviewed_on` (a `YYYY-MM-DD` date).

Then, if any page's `data_as_of` differs from the file's, it returns `{}`: last month's
headlines are dropped, never shown against new data, and are not checked further.
Otherwise, for each asset with an entry, in list order: there must be exactly one page for
it; `reviewed_on` must not be before that page's `generated_on` (a headline can't be
reviewed against numbers that didn't exist yet); and `check_headline(text, claims, page,
registry)` must return no problems. The error names the asset and the failing rules. An
approved headline that fails is an error, never silently dropped or published.

### 15.3 Drafting: `draft_request`, `read_draft`, `http_post_json` and `scripts/draft_headlines.py`

The model drafts, code checks, Avi reviews. Avi's decisions (30 Sept):
- The model sees only the page's own approved sentences from cards 1 to 3 whose figures are all the asset's observed history, and may cite only those figures. Card 5's figures are comparisons with the tracker by nature. Card 6 exists only for dollar assets, so headlines would not be like-for-like.
- One attempt per asset, with no automatic retry. Feeding the checker's complaints back to the model would train it to satisfy the checker, not to be right.
- Every draft, with its problems, goes to `words/headline_drafts.json`. Avi commits it as the record of what the model proposed.
- He can redraft only the assets he names.
- Amended the same morning, after review rejected 6 of the 7 first drafts (all passed the checker): prompt version 2 adds rule 6 (date a fall, never rank it), rule 12 bans superlatives, and time to recover is only ever offered from the high (`worst.months_underwater`). The from-the-low figure is the flattering one, and the first drafts mixed the two, which reversed a comparison between pages.
- Amended again after review of the second drafts: the four dollar assets' headlines gave falls in pounds without saying so. Prompt version 3 adds rule 3 and an input line for a dollar asset (below), and the checker's rule 16 requires "in pounds" (or "in dollars") on a dollar asset.

Only derived figures already on the page are sent, and the request asks OpenAI not to store the response.

**Where the code lives.**
- `words/headline.py`, pure like the rest of the module: `DRAFT_MODEL = "gpt-6.1-sol"`, `PROMPT_VERSION = "3"`, `DRAFT_INSTRUCTIONS`, `draft_request(page)` and `read_draft(response)`. It may import `json`, to read the model's answer.
- `pipeline/network.py`: `http_post_json(url, headers, body)`, next to `http_get_json` (section 9.7). It is still the only module that opens a connection.
- `scripts/draft_headlines.py`: the command Avi runs, with his key. Its `main()` has no default arguments, and the script imports `pipeline.network` only under `if __name__ == "__main__":`. So a test that forgets its fake fails instead of reaching the network.

#### 15.3.1 The request: `draft_request(page)`

`page` is a section 13 page. `draft_request` returns a new dictionary: the JSON body of one request to OpenAI's Responses API.

| Key | Value |
|---|---|
| `model` | `"gpt-6.1-sol"` |
| `instructions` | `DRAFT_INSTRUCTIONS` (below) |
| `input` | The page text (below) |
| `text` | `{"format": {"type": "json_schema", "name": "headline", "strict": true, "schema": <schema>}}` |
| `reasoning` | `{"effort": "medium"}`. This is the model's default, fixed so that a change of default can't change the drafts. |
| `max_output_tokens` | `8000`. Reasoning counts toward it, and it bounds what one request can cost. |
| `store` | `false` |

**What the model is given.** Only the cards `bumpy`, `worst` and `panic` (cards 1 to 3) are read, in the page's card order.
- The *offered sentences* are the sentences of those cards, in order, that cite at least one claim and whose every cited claim has series `asset` and kind `observed`.
- A sentence of those cards that cites an id which is not one of the page's claims is a `WordsError`: `<id> is not a claim on the page.`
- The *offered claims* are the claims the offered sentences cite, except `worst.months_to_recover`, each once, in the order first cited. The recovery sentence is still offered, but time to recover is only ever offered counted from the high.
- If there are no offered claims: `WordsError("page has no figures to cite.")`.
- The recovery state is rule 15's, from all the page's claims.

`input` is these lines, joined with `\n`, with no line break at the end:

```
Investment: <the instrument's label>
Full name: <its identity name>
Ticker: <its identity ticker>
<the pounds line, for a dollar asset only>
<data_as_of_text>.

What its page says:
<card title>
- <sentence text>

Figures you may cite (id | figure | direction | period):
<id> | <display> | <direction> | <Mon YYYY> to <Mon YYYY>

<recovery line>
```

- The pounds line is `Every figure here is in pounds, but it trades in US dollars.`, written only when the page's instrument trades in `USD` (its identity `trading_currency`). For an asset that trades in pounds there is no such line.
- A card's title is written only if the card has an offered sentence. Each such card is followed by its offered sentences, in order.
- There is one figure line per offered claim, in order. The direction is `none` when the claim has none. The period is `period_start` and `period_end` written with `month_name`.
- The recovery line depends on the recovery state:
  - not recovered: `Its largest fall had not recovered by the end of the data.`
  - recovered: `Its largest fall recovered.`
  - no fall: `It had not fallen below a previous high at any month-end.`

The schema is below. With `strict`, the model can return only this shape and can cite only an offered claim. Everything else, including citing one or two claims and all of the wording, is left to the checker.

```json
{"type": "object",
 "properties": {"text": {"type": "string"},
                "claims": {"type": "array", "items": {"type": "string", "enum": ["<the offered claim ids, in order>"]}}},
 "required": ["text", "claims"],
 "additionalProperties": false}
```

`DRAFT_INSTRUCTIONS` (version 3, approved by Avi on 30 Sept) is the text below, filled in with Python's `str.format`. The placeholders are:
- `{down}` and `{up}`: rule 14's lists.
- `{recovery}`: rule 15's list.
- `{advice}`, `{future}`, `{number}`, `{comparison}` and `{loaded}`: the lists of rules 8 to 12.

Each list is written out in section 15.1's order, joined by `, `. It is built from the checker's own lists, never retyped, so the prompt and the checker can't drift apart. The golden file holds the full text.

```
You write the headline for one page of a website that explains, in plain English, how one investment behaved in the past. Its readers are UK investors. The page describes history and never gives advice. Code checks your headline, and then a person reviews it before it is published.

Write one sentence that gives the gist of what holding this investment was like, using one or two of the figures you are given. Return the sentence as "text" and the ids of the figures it uses as "claims".

Rules:
1. One sentence in the past tense, at most 30 words, ending with a full stop. No semicolons, question marks or exclamation marks.
2. Cite one or two figures, and write every figure you cite exactly as given, such as 35.5% or £6,450. Put no plus or minus sign in front of a figure: say the direction in words.
3. If the input says the investment trades in US dollars, write "in pounds" in the sentence: every figure is in pounds, and a fall in pounds can be very different from the same fall in dollars.
4. Use no other numbers. The only exceptions: the first and last months of a cited figure's period, written exactly as given (Feb 2009, never February 2009); £10,000 when citing a figure about £10,000 invested; and "2022 rate shock" when citing that period's figure.
5. If a cited figure's direction is down, use one of these words: {down}. If it is up, use one of these: {up}.
6. Describe this investment alone. Do not compare it with anything, and do not name any other investment, fund, index or tracker.
7. Do not rank a fall. The data starts at a fixed month, so a fall can't be called the largest, worst or deepest. Say when it happened instead, using its first and last months.
8. Words about recovery ({recovery}) must agree with the page. If its largest fall had not recovered, put "not" just before them, as in "had not recovered". If it recovered, never negate them. If it had not fallen below a previous high, do not use them.
9. Never use these words or phrases:
- advice: {advice}
- the future: {future}
- numbers in words: {number}, or any word ending in "fold"
- comparisons: {comparison}
- loaded words: {loaded}
```

#### 15.3.2 Reading the answer: `read_draft(response)`

`response` is the parsed JSON of a Responses API reply. `read_draft` returns `{"text", "claims", "drafted_by"}`, or raises a `WordsError` whose message never includes the model's text or the response. The checks, in this order:

1. The response is a dictionary. Otherwise: `response is not an object`.
2. `status` is `"completed"`. Otherwise the message is `status <status>`:
   - `<status>` is the value if it is an *identifier* (text of 1 to 64 characters, each `a` to `z`, `0` to `9` or `_`), and `unreadable` if not.
   - It is followed by ` (<reason>)`, using the first identifier among `incomplete_details.reason` and `error.code`. Each is read only if its parent is a dictionary.
   - For example, `status incomplete (max_output_tokens)` means the token cap was hit.
3. `model` is text, not empty, with no whitespace at either end. Otherwise: `model missing`. It becomes `drafted_by`: the model that actually answered, which may be a dated version of `gpt-6.1-sol`.
4. `output` is a list. Otherwise: `output missing`.
   - The *answers* are its items that are dictionaries with `type` `"message"` and a `phase` other than `"commentary"`. A missing phase counts: newer models may send commentary messages before the final answer.
   - There must be exactly one answer. Otherwise: `<n> answers`.
5. The answer's `content` is a non-empty list. Otherwise: `answer has no content`.
   - If any item is a dictionary with `type` `"refusal"`: `the model refused`.
   - Otherwise every item must be a dictionary with `type` `"output_text"` and text in `text`. If not: `unexpected content`.
   - The answer is their `text`s, joined in order.
6. The answer is JSON for a dictionary with exactly the keys `text` and `claims`. Otherwise: `answer is not a headline object`.

`text` and `claims` are returned as given, whatever their types. `check_headline` reports a bad text or claims list (rules 1 and 2).

#### 15.3.3 The connection: `http_post_json(url, headers, body)`

`http_post_json` makes one POST and returns the parsed JSON:
- The body is `json.dumps(body, allow_nan=False)` in UTF-8. A body that can't be written that way is an error raised before anything is sent.
- The headers are as given.
- The timeout is 120 seconds, because the model reasons before answering.
- Certificate checking is Python's default: never a `context`.

Errors are `ProviderError`, as in section 9.7, and never show the URL, a header, the body or the response:

| Problem | Message |
|---|---|
| An HTTP error status | `HTTP <code>`, then ` (<detail>)` if the error's body is JSON whose `error` is a dictionary with an identifier (15.3.2) in `code`, or failing that in `type` |
| A timeout (`socket.timeout` or `TimeoutError`, raised directly or as a `URLError`'s reason) | `timed out` |
| Any other connection failure | `connection problem (<error type>)` |
| A body that isn't JSON | `response was not JSON` |

OpenAI's error codes say what to fix: `invalid_api_key`, `insufficient_quota` when the $5 limit is reached, `model_not_found`. Its error messages can quote part of the key, so they are never shown. Reading the error's body never raises: any failure just leaves the detail out. `http_get_json` doesn't change.

#### 15.3.4 The command: `python3 scripts/draft_headlines.py [--list | <asset id> ...]`

`main(argv, environ, today, root, out, post)` returns the exit code and writes lines to `out`. `post(url, headers, body)` sends one request; only the script's entry point passes `http_post_json`. The command never prints a traceback, the key, a request or the model's text.

Every `FAILED:` line is followed by a second line, and exit code 1:
- `Nothing was sent or written.` if no request had been sent.
- Otherwise `Nothing was written. <k> request(s) sent.` (`1 request`, `2 requests`), where `<k>` counts every call to `post`, including one that failed.

Error messages have the form `<who>: <step>: <ErrorType>: <message>`. The message is included only for `RegistryError`, `WordsError` and `ProviderError`, whose messages are value-free by design; any other type is named alone.

1. **Arguments:** none (every asset), `--list` on its own, or one or more different asset ids, none starting with `-`. Anything else prints `Usage: python3 scripts/draft_headlines.py [--list | <asset id> ...]` and returns 2.
2. **Instrument list:** `root/pipeline/instruments.json`, read as UTF-8 with `json.load` (`FAILED: registry: load: <ErrorType>`), then `check_registry` (`FAILED: registry: check: <ErrorType>[: <message>]`).
3. **Assets:** each named id, in the order given, must be an asset in the list. Otherwise: `FAILED: <name> is not an asset in the instrument list.` The assets are drafted in the list's order, whatever order they were named in.
4. **Pages**, for each asset in list order, finishing one asset before the next:
   - Load `root/site/data/<id>.json` (`FAILED: <id>: load: <ErrorType>`).
   - Its `instrument` `id` must be the asset: `FAILED: <id>: page: not this asset's page`, also when the id can't be read.
   - Its `data_as_of` and `generated_on` must equal the first asset's: `FAILED: <id>: page: data_as_of or generated_on differs`.
   - Then `draft_request(page)` (`FAILED: <id>: request: <ErrorType>[: <message>]`).

   The pages are the site's published pages, so drafts are written against exactly what each page shows.
5. **`--list`** stops here. It has sent nothing and needs no key. It prints three lines and returns 0:
   - `Plan: <n> request(s) to gpt-6.1-sol, one per asset: <ids in list order, joined by ", ">.`
   - `Pages: data as of <data_as_of>, generated on <generated_on>.`
   - `No requests made.`
6. **Key:** `QX_OPENAI_API_KEY` from `environ`.
   - Missing or empty: `FAILED: QX_OPENAI_API_KEY is not set in this terminal.`
   - Anything but letters, digits, `-` and `_` (a pasted space or line break): `FAILED: QX_OPENAI_API_KEY is not a valid key.`
7. **Drafts**, for each asset in list order:
   - `post("https://api.openai.com/v1/responses", {"Authorization": "Bearer <key>", "Content-Type": "application/json"}, body)` (step `post`).
   - Then `read_draft` (step `response`).
   - Then `check_headline(text, claims, page, registry)` (step `check`).

   The draft is `{"text", "claims", "drafted_by", "problems"}`, where `problems` is `check_headline`'s list as returned. A draft with problems is recorded, not an error. The first error stops the run.
8. **Write** `root/words/headline_drafts.json`, all or nothing. The value has these keys:
   - `data_as_of` and `generated_on`: the pages'.
   - `drafted_on`: `today`, as `YYYY-MM-DD`.
   - `model`: `"gpt-6.1-sol"`.
   - `prompt_version`: `"3"`.
   - `drafts`: asset id to draft.

   It is written as `json.dumps(value, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False) + "\n"` in UTF-8, to `headline_drafts.json.tmp`, replacing any left over. That file is read back, parsed, and must equal the value (`FAILED: drafts: write: read back differently`). Then it is renamed over `headline_drafts.json`. Any failure removes the temporary file (`FAILED: drafts: write: <ErrorType>[: <message>]`), and the previous drafts file is left as it was.
9. **Success** prints these lines and returns 0:
   - `Drafted <n> headline(s) with gpt-6.1-sol for data as of <data_as_of>.`
   - One line per draft, in list order: `<id>: passes the checks`, or `<id>: fails <rules>`, where `<rules>` are the rule names of its problems, each once, in the order they first appear, joined by `, `.
   - `Wrote words/headline_drafts.json. Review every draft before copying it into words/headlines.json.`

Anything else that goes wrong prints `FAILED: unexpected <ErrorType>.`, followed by the second line as above.

`words/headline_drafts.json` is generated output, and the page writer never reads it. The only route to a page is Avi copying a draft into `words/headlines.json` (section 15.2), adding `reviewed_on`, and committing it. Avi commits the drafts file with it, as the record of what the model proposed.

### 15.4 Publishing approved headlines

The page writer (section 14) is the only route from `words/headlines.json` to a page. After
building every page, and before the index, it runs `check_approvals` against those pages
(section 14.1 step 6):

- An approved headline appears on its page exactly as approved: `text`, `claims`,
  `drafted_by` and `reviewed_on`, so the page records who drafted it and when it was
  reviewed.
- An asset without one gets none: its `headline` stays null.
- If the file is for another month, every page is written without a headline, and the
  command says so. Old words never sit on new numbers.
- An approved headline that fails any check stops the run, and nothing is written. It is
  never published, and never silently dropped.
- The file is required. A missing file is a mistake, not an absence of headlines; an empty
  set is `{"data_as_of": "<month>", "headlines": {}}`.

Each month, in order: refresh the data (section 10); build the pages, which then have no
headlines; draft against those pages (15.3); review and approve (15.2); build the pages
again, now with headlines; commit `site/data`.

## 16. The site pages

In `web/render.py` (package `web`, with an empty `__init__.py`). Pure, like sections 11 to
13: it turns the site's data (section 13: `index.json` and one page per asset) into
finished HTML, as text. Every word and number a visitor can see or hear is in that HTML
before any JavaScript runs. JavaScript (a later task) only moves, filters, shows and hides
what is already there; it never writes text, apart from the count-up in a figure, which
ends by showing the exact text the HTML already holds. It imports only `datetime`, `html`,
`math` and `re` (the pure-module check in `tests/test_invariance.py` covers it): no
network, no files, no environment variables, no clock. The same inputs always give the
same text, and the inputs are never changed.

`render_page(page, index)` returns one asset's page and `render_landing(index, pages)` the
landing page, each a `str`. Errors are a `SiteError`, defined in `web/render.py`, with the
messages in section 16.6.

### 16.1 Fixed values and formats

- `SITE_NAME` is `"Quant Eyes"` (named 30 Sept 2026; Task 10b replaced the working title
  "Quant explainer" here and in the golden cases). `HEADLINE_RULE_COUNT` is `16`,
  the number of rules in section 15.1; a test checks it against the rule names used in
  `tests/golden/headline.json` (section 16.8).
- **Month:** `YYYY-MM` is written `Mon YYYY` (`2007-12` → `Dec 2007`), with the months
  `Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec`.
- **Period** of a claim: `{Mon YYYY of period_start} to {Mon YYYY of period_end}`
  (`Dec 2007 to Feb 2009`).
- **Day:** `YYYY-MM-DD` is written `{day} {Mon} {YYYY}` with no leading zero
  (`2026-09-30` → `30 Sep 2026`).
- **Count word:** the number of assets in the index as a word: `one` to `twelve`. The
  index must have from 2 to 12 assets.
- **Direction words** for a claim with a direction: `up {display}`, `down {display}`, or
  `unchanged ({display})` for `flat` (the same words as section 11.5).
- **Size:** a number from 0 to 1 that sets the length or position of part of a visual.
  It is written with `format(x, ".4f")` of the Python float, in the element's `style`
  attribute and nowhere else: `style="--qx-size:0.2750"`. A size that is not a finite
  number from 0 to 1 is a `SiteError`.
- **Escaping:** every piece of text taken from the data or from this section is written
  with `html.escape(text, quote=True)`, in element text and in attribute values alike.
- Sizes use claim `value`s only. No number is shown that is not a claim's `display`, a
  count from section 16.1, a date from the data, or fixed copy below.

### 16.2 The contract: reading a page back

The tests never compare HTML text. They read a page back into a list of **entries** and
compare that list with the golden file, so the markup, class names and layout are free
(Task 9b styles them) while every word, its order and every size are fixed.

- Every element that holds text for the visitor carries `data-qx="<role>"` and, where the
  role repeats on a page, `data-qx-key="<key>"`. The pair (role, key) is unique on a page.
- An element whose text is an attribute (a `<meta>` description, an input's placeholder,
  an icon button's `aria-label`) also carries `data-qx-attr="<attribute name>"`.
- A `size` element is an empty element with `data-qx="size"`, a key, and the style above.
- `data-qx` elements never contain another `data-qx` element.

**Reading back** uses `html.parser.HTMLParser` with `convert_charrefs=True`. Each start tag
with a `data-qx` attribute begins an entry, in document order:
`[role, key, text, size]`, where

- `key` is the `data-qx-key` value, or `""` without one;
- `text` is the value of the attribute named by `data-qx-attr` if there is one; otherwise
  all character data inside the element, up to its matching end tag (a void element such
  as `<meta>` or `<input>` has none). In both cases every run of the characters space, tab,
  newline, carriage return and form feed becomes one space, and the result is stripped;
- `size` is the number in `style="--qx-size:<n>"` as written (text, e.g. `"0.2750"`), or
  `null` when the element has no `style` attribute.

### 16.3 Parts every page shares

**Head**, in this order:

```html
<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title data-qx="title">{title}</title>
<meta name="description" data-qx="description" data-qx-attr="content" content="{description}">
<meta property="og:title" data-qx="og-title" data-qx-attr="content" content="{title}">
<meta property="og:description" data-qx="og-description" data-qx-attr="content" content="{description}">
<meta property="og:type" content="website">
<link rel="stylesheet" href="{prefix}assets/site.css">
<link rel="icon" type="image/svg+xml" href="{prefix}assets/brand/favicon.svg">
<script src="{prefix}assets/site.js" defer></script>
</head>
```

`{prefix}` is empty on the landing page and `../` on an asset page (each asset page will
be `site/<id>/index.html`, written by a later task). Task 9b may add `<link>` elements
whose `rel` is `stylesheet` or `preload` with an `href` under `{prefix}assets/`. The icon
link above is the only one whose `rel` is `icon` (Task 10b; `tests/test_brand.py`).

**Header:** a link to the landing page (`href="./"` on the landing page, `"../"` on an
asset page) with role `site-name` and the text `SITE_NAME`; then role `not-advice`:
`Not advice`.

**Footer**, in this order:

1. `footer-data`: `{data_as_of_text} · Method {method_version}`.
2. `sources-label`: `Sources`.
3. One link per source, role `source`, key the provider's name, `href` its `url`, text
   `{provider} ({used_for, joined with ", "})`. On an asset page these are the page's
   `sources` in order. On the landing page they are merged across the pages in index
   order: each provider once, where it first appears, with its `used_for` labels in the
   order they first appear.
4. Asset page only: `identity`: `{identity name}`, followed by ` · ISIN {isin}` when the
   ISIN is not empty. Then, if the identity has sources: `identity-label`: `Identity from`,
   and one link per source URL, role `identity-source`, key `1`, `2`, … in order, `href`
   the URL, text its host: the part after `https://` up to the next `/`, or to the end
   (`https://etp.morganstanley.com/fr/en/…` → `etp.morganstanley.com`).
5. `disclaimer`: `Past results in pounds, measured at month-ends. Descriptive, never
   advice. Past behaviour does not predict future results.`

### 16.4 An asset page: `render_page(page, index)`

The title is `{label}, in pounds · {SITE_NAME}`; the description is the headline's text
if the page has a headline, otherwise the tagline (section 16.5). `{label}` is the
instrument's label and "the tracker's label" is the benchmark's. Then, in this order:

1. `back`, a link to `../`: `All investments` (Task 10f: the site never states how many
   investments it covers).
2. `kicker`: the type (`share` → `Share`, `etf` → `Exchange-traded fund`, `etc` →
   `Exchange-traded commodity`, `cryptocurrency` → `Cryptocurrency`), followed by
   ` · {exchange}` when the exchange is not empty.
3. `asset-label`, the page's only `<h1>`: `{label}`.
4. `asset-name`: `{identity name} · {ticker}`.
5. Tags, role `tag`: key `priced`: `Priced in US dollars` (trading currency `USD`) or
   `Priced in pounds` (`GBP`); key `figures`: `Figures in pounds`; key `data`:
   `{data_as_of_text}`.
6. The headline. `section-label`, key `headline`: `The headline`. With a headline:
   `headline`, key the asset id: its text; then three steps, each a `chain` and a
   `chain-detail` with the same key: `drafted`: `Drafted by AI` and `{drafted_by}`;
   `checked`: `Checked by code` and `{HEADLINE_RULE_COUNT} of {HEADLINE_RULE_COUNT} rules
   passed`; `reviewed`: `Reviewed by a person` and the day of `reviewed_on`. Without one:
   `no-headline`: `No reviewed headline for this data yet. A headline appears here only
   after a person has reviewed it.`
7. The questions, in a `<nav>`. `rail-label`: `The questions`. For each card in order, a
   link to `#{card id}` holding `rail-number` (`01` to `06`) and `rail-title` (the card's
   title), both keyed by the card id. Then `compared-label`: `Compared with`;
   `benchmark-label`: the tracker's label; `benchmark-name`: `{benchmark identity name} ·
   {benchmark ticker}`.
8. The six cards, each a `<section id="{card id}">` starting with `card-number` (`01` to
   `06`) and `card-title` (an `<h2>`: the card's title), keyed by the card id. The rest
   of each card, in order, where `sentence` `{card}.{i}` is the card's sentence number
   *i* counting from 0, keyed `{card id}.{i}`:
   - **bumpy.** `figure`, key `bumpy.volatility`: its display. Sentence 0. The bars: the
     asset's bar is `bumpy.volatility_common` if the page has it, otherwise
     `bumpy.volatility`, and the tracker's is `bumpy.tracker_volatility`; `bars-label`:
     `Same months: {period of the asset's bar}`; then for the asset (key `bumpy.asset`)
     and the tracker (key `bumpy.tracker`): `bar-label` (the label, or the tracker's
     label), `bar-value` (the claim's display) and a `size`: the claim's value divided by
     the larger of the two values, so the longer bar is 1. Sentences 1 and 2. The maths.
   - **worst**, when the page has `worst.fall`: `figure`, key `worst.fall`. Sentence 0.
     The £10,000 bar: `drain-label`: `£10,000 invested at the high`; `figure`, key
     `worst.ten_thousand_left`, with the attribute `data-qx-from="10000"` (the only place
     it appears): its display; `drain-period`: the period of `worst.fall`; `size`, key
     `worst.drain`: the value of `worst.ten_thousand_left` ÷ 10000; `drain-left`:
     `{£ left display} at the low`; `drain-lost`: `{£ lost display} less`. The timeline,
     where *low* is `worst.months_to_low` and *under* is `worst.months_underwater`:
     - Recovered (the page has `worst.months_to_recover`, *rec*): `timeline-label`: `High
       to back at the high: {under display}`; `segment`, key `worst.fall`: *low*'s
       display, with a `size` of the same key: *low* ÷ *under*; `segment`, key
       `worst.recovery`: *rec*'s display, with a `size`: *rec* ÷ *under*; then three
       points, each a `point-label` and a `point-date` with the same key: `high`: `High`
       and `end of {Mon YYYY of worst.fall's period_start}`; `low`: `Low` and `end of
       {Mon YYYY of worst.fall's period_end}`; `back`: `Back at the high` and `end of {Mon
       YYYY of rec's period_end}`.
     - Not recovered (the page has `worst.below_high_at_end`, *below*): `timeline-label`:
       `Below its high: {under display}, to the end of {Mon YYYY of under's period_end}`;
       `segment`, key `worst.fall`, with its `size`, as above; `segment`, key
       `worst.since-low`: `still {below display} below its high`, with a `size`: (*under*
       − *low*) ÷ *under*; points `high` and `low` as above, and `end`: `Not recovered by`
       and `end of {Mon YYYY of under's period_end}`.

     Then sentences 1, 2 and 3. The maths. When the page has no `worst.fall` (section
     11.4's one sentence): sentence 0, then the maths.
   - **panic.** For each window in order (`gfc`, `covid`, `rate_shock`, number *w* from 0):
     sentences 2*w* and 2*w* + 1; for the first window only, `chips-label`: `Over the
     period`; then `chip-label` and `chip-value`, key `{window}.asset`: the label, and the
     direction words of `panic.{window}`, or `not covered` if the page has no such claim;
     then `chip-label` and `chip-value`, key `{window}.tracker`: `Tracker`, and the
     direction words of `panic.{window}.tracker`, or `not covered`. Then sentence 6. The
     maths.
   - **next.** `figure`, key `next.correlation`. Sentence 0. The scale: `scale-label`:
     `Correlation with the tracker`; `scale-value`, key `next.correlation`: its display;
     `size`, key `next.correlation`: (value + 1) ÷ 2; then `scale-mark` and `scale-note`
     keyed `low`: `−1` (true minus sign) and `always opposite`, `mid`: `0` and `no
     pattern`, `high`: `1` and `always in step`; `range`: `Range across 36-month
     stretches: {next.rolling_lowest display} to {next.rolling_highest display}`; `size`,
     key `next.range-low`: (lowest value + 1) ÷ 2; `size`, key `next.range-high`: (highest
     value + 1) ÷ 2. Sentences 1 and 2. The 90/10 bar: `mix-part`, key `next.tracker`:
     `Tracker 90%`, with a `size` of the same key: 0.9; `mix-part`, key `next.asset`:
     `{label} 10%`, with a `size`: 0.1. Sentences 3 to the last. The maths.
   - **pound** and **limits**: their sentences, in order.

**The maths** of a card, in a `<details>` element: `maths-show`: `Show the maths` and
`maths-hide`: `Hide the maths` (with the `hidden` attribute), both inside its `<summary>`;
`maths-method`: the card's method text, below. For bumpy and worst only, when the card
has claims, a table: `maths-head` keyed `{card}.figure`, `{card}.value`, `{card}.period`:
`Figure`, `Value`, `Period`; then one row per claim whose id starts with `{card}.`, in the
page's claims order: `maths-figure` (its label, below), `maths-value` (its display) and
`maths-period` (its period), each keyed by the claim id. Then `maths-note`: `Periods run
from month-end to month-end. Each figure is rounded once, from the unrounded
calculation.` and `maths-sources`: the sources line. All keyed by the card id unless
said otherwise.

Table labels: `bumpy.volatility` `Volatility, a year`; `bumpy.volatility_common` `Same
months as the tracker`; `bumpy.tracker_volatility` `The tracker, same months`;
`worst.fall` `Largest fall since {Mon YYYY of bumpy.volatility's period_start}`;
`worst.months_to_low` `High to low`; `worst.ten_thousand_left` `£10,000 at the high,
worth at the low`; `worst.ten_thousand_lost` `£10,000 at the high, less at the low`;
`worst.months_to_recover` `Low to back at the high`; `worst.months_underwater` `Time below
the high`; `worst.below_high_at_end` `Still below its high at the end`.

Method texts (approved by Avi, 30 Sept):

- bumpy: `A month's return is the change in value from one month-end to the next, in
  pounds, with any income reinvested. Volatility is the standard deviation of those
  monthly returns (the sample version, dividing by one fewer than the number of months),
  multiplied by √12 to make it a yearly figure. That step treats months as independent,
  which is an approximation.`
- worst: `At each month-end the value is compared with the highest month-end value so
  far. The largest fall is the deepest drop below that high; if two are equally deep, the
  earlier counts. The first month in the data counts as a high, so a fall that began
  earlier is measured only from there. The high is the last month-end at that level
  before the low; back at the high is the first month-end at or above it. Months are
  counted between month-ends. The £10,000 figure is £10,000 × (1 − the fall), rounded to
  the nearest £10.`
- panic: `Each window runs from the month-end before it starts to the month-end it
  finishes: the 2022 rate shock runs from the end of Dec 2021 to the end of Oct 2022. The
  figure is the change between those two month-ends, not the largest fall inside the
  window. A window is shown only if the data covers both month-ends; it is never
  shortened to fit.`
- next: `Correlation is the Pearson correlation of the two sets of monthly returns in
  pounds, over the months both cover. The 36-month range repeats it for every run of 36
  consecutive months and shows the lowest and highest. The 90/10 mix starts at 90%
  tracker and 10% this investment; each part grows or shrinks with its own returns, and
  at the end of every December the mix is reset to 90/10. A yearly figure is the total
  return turned into a compound rate: (1 + total return)^(12 ÷ months) − 1. Before fees,
  with no trading costs or tax.`

(`√` is U+221A, `×` U+00D7, `÷` U+00F7 and `−` U+2212.)

**The sources line** of a card names only the data its figures use. The labels needed
are: the asset's label; the tracker's label if any claim whose id starts with `{card}.`
has series `tracker` or `mix`; and, for an asset whose trading currency is `USD`, every
`used_for` label that is neither the asset's nor the tracker's (the exchange rate). For
each source in the page's order, keep its `used_for` labels that are needed, in their
order; leave out a source with none. The line is `Source: ` (one source kept) or
`Sources: ` (more), then each kept source as `{provider} ({labels, joined with ", "})`,
joined with `; `, then `. Method {method_version}.`

### 16.5 The landing page: `render_landing(index, pages)`

Landing v2 (Task 10c, copy approved 30 Sept 2026). `pages` is the list of asset pages in
the index's order. The title is `{SITE_NAME}: investments in plain English`;
the description is the landing tagline: `Plain-English explanations of how
investments have behaved, in pounds. Every figure comes from tested code. The one line an
AI writes is checked against {HEADLINE_RULE_COUNT} rules and read by a person before it
goes live.` (Asset pages keep their own description, section 16.4.) Then, in this order:

1. `kicker`: `A governed AI demo · in pounds` (the stylesheet
   sets it in capitals; the text is as written here).
2. `hero`, the page's only `<h1>`: `AI drafts it. Code checks it. A person signs it off.`
3. `tagline`: the landing tagline.
4. The search: in an element with the `hidden` attribute (JavaScript shows it):
   `search-label`, a `<label>` for the input: `What am I actually getting into?`;
   `search-hint`, a search input whose `placeholder` is the text: `Try {first asset's
   label} or {first asset's ticker}`; then for each asset in order, a list item with the
   `hidden` attribute holding a link to `{id}/` with `result-label`, `result-ticker` and
   `result-name` (the index's label, ticker and name), keyed by the asset id; then, in an
   element with the `hidden` attribute, `not-covered-title`: `Not covered yet` and
   `not-covered-text`: `Each investment here is covered in depth: every figure comes from
   tested code, and every headline is reviewed by a person.` (No `search-count`: the site
   never states how many investments it covers.)
5. The headlines, only if at least one page has a headline, for the assets that have
   one, in index order (number *k* of *m*): `section-label`, key `headlines`:
   `In one line`; then for each, keyed by the asset id: `slide-position`: `{k} / {m}`;
   `slide-label`: the label; `slide-ticker`: the ticker; `headline`: its text; the
   **audit row**: `audit-drafted`: `Drafted by {drafted_by}`, `audit-checked`:
   `{HEADLINE_RULE_COUNT} of {HEADLINE_RULE_COUNT} rules`, `audit-reviewed`: `Reviewed
   {day of reviewed_on}`; `slide-open`, a link to `{id}/`: `Open {label}`. (The landing
   page no longer has the `chain` roles; asset pages keep theirs.) Then, in an element
   with the `hidden` attribute: a button holding `pause`: `Pause the headlines` and
   `play`: `Play the headlines` (with the `hidden` attribute); then for each headline an
   empty button, role `segment`, key the asset id, `data-qx-attr="aria-label"`, whose
   `aria-label` is `Show the headline for {label}`.
6. The **gates**, always (with or without headlines): `gates-title`: `How a headline
   gets published`; then three gates, keyed `01`, `02`, `03`, each `gate-number` (the
   key), `gate-title` (an `<h3>`) and `gate-text`:
   - `01`: `Drafted by AI`; `A model writes one line per investment. It sees only
     figures from that investment's own page, and can cite only those.`
   - `02`: `Checked by code: {HEADLINE_RULE_COUNT} rules`; `No advice, no forecasts, no
     rankings, every number traced to the page. One failure and the line is out.`
   - `03`: `Reviewed by a person`; `In the first round, all 7 drafts passed every code
     check. A person rejected 6. Most reasons became new rules. The rest are why a person
     stays in the loop.` (A dated fact about the launch review, 30 Sept 2026, so its
     numbers are fixed copy. `A person rejected 6.` may be wrapped in `<strong>`.)
   The links "The full method and evidence →" and "See the audit trail →" are added by
   Tasks 10e and 10d, not here.
7. `tiles-label`: `Or pick one`; then for each asset, a link to
   `{id}/` holding `tile-ticker` and `tile-label`, keyed by the asset id.

There is no `strip` on the landing page any more. The labels, names and tickers on the
landing page come from the index; everything else from the pages.

### 16.6 Checks and errors

Both functions check before writing anything, in this order, and raise a `SiteError` with
the first failure's message. Messages never contain a figure.

**The index** (both functions): the keys `assets`, `benchmark`, `data_as_of`,
`data_as_of_text`, `generated_on` and `method_version` (`index: missing <key>`); from 2 to
12 assets (`index: assets: count`); each with non-blank `id`, `label`, `name`, `ticker`
and `type` (`index: assets: missing <field>`); no id twice (`index: assets: duplicate
<id>`).

**The landing page** then checks that the pages' instrument ids are the index's ids in
the same order (`landing: pages do not match the index`), then checks each page as below,
then merges the sources (a provider with two different URLs: `landing: sources:
<provider> url differs`).

**A page**, where `<id>` is its instrument's id:

1. The keys `instrument`, `benchmark`, `data_as_of`, `data_as_of_text`, `generated_on`,
   `method_version`, `sources`, `cards`, `claims` and `headline` (`page: missing <key>`).
2. The id is in the index (`<id>: not in the index`).
3. `data_as_of`, `data_as_of_text`, `generated_on` and `method_version` equal the index's
   (`<id>: <key> differs from the index`); then the label, the identity name and the
   ticker equal the index entry's `label`, `name` and `ticker` (`<id>: label differs from
   the index`, `<id>: name …`, `<id>: ticker …`).
4. Identity: a known type (`<id>: identity: type`); trading currency `USD` or `GBP`
   (`<id>: identity: trading_currency`); every identity source URL starts with
   `https://` and has no whitespace (`<id>: identity: sources`).
5. Each source has a non-blank `provider` (`<id>: sources: provider`), a URL as above
   (`<id>: sources: url`) and a non-empty list of non-blank `used_for` labels (`<id>:
   sources: used_for`).
6. The card ids are exactly `bumpy`, `worst`, `panic`, `next`, `pound`, `limits` in that
   order (`<id>: cards: order`); each card has a non-blank title and at least one
   sentence, each with non-blank text (`<id>: cards: <card id>`).
7. No claim id twice (`<id>: claims: duplicate <claim id>`).
8. bumpy has 3 sentences (`<id>: bumpy: sentences`); `bumpy.volatility` and
   `bumpy.tracker_volatility` exist (`<id>: claims: missing <claim id>`); the asset's bar
   claim and the tracker's have the same `period_start` and `period_end` (`<id>: bumpy:
   periods differ`).
9. worst: with `worst.fall`, the page has `worst.months_to_low`,
   `worst.ten_thousand_left`, `worst.ten_thousand_lost` and `worst.months_underwater` and
   exactly one of `worst.months_to_recover` and `worst.below_high_at_end`; without it, no
   claim starting `worst.` (either way `<id>: worst: claims`). Then 4 sentences with
   `worst.fall`, 1 without (`<id>: worst: sentences`).
10. panic has 7 sentences (`<id>: panic: sentences`); every `panic.{window}` and
    `panic.{window}.tracker` claim has direction `up`, `down` or `flat` (`<id>: claims:
    direction <claim id>`).
11. `next.correlation`, `next.rolling_lowest` and `next.rolling_highest` exist (`<id>:
    claims: missing <claim id>`); next has 6 or 7 sentences (`<id>: next: sentences`).
12. The headline is null, or an object (`<id>: headline: shape`) with non-blank `text`
    and `drafted_by` (`<id>: headline: text`, `<id>: headline: drafted_by`) and a real
    date `YYYY-MM-DD` in `reviewed_on` (`<id>: headline: reviewed_on`).
13. While the page is written, any size that is not a finite number from 0 to 1, or a
    division by zero, is `<id>: size: <size key>` (the bumpy bars check `bumpy.asset`
    first).

### 16.7 What the markup may contain

Checked by the tests on every page and landing page the golden cases produce:

- It starts `<!doctype html>\n<html lang="en-GB">\n` and ends `</html>\n`.
- Exactly one `<title>` and one `<h1>`; every `card-title` is an `<h2>`.
- The only `<script>` is the one in the head, with exactly `src` and `defer`. No `<style>`
  element, no comments, no attribute starting `on`, and no `style` attribute except on
  `size` elements, where it is exactly `--qx-size:<digit>.<4 digits>`.
- Only these elements: `html head meta title link script body header main footer nav
  section article div span p a h1 h2 h3 ul ol li dl dt dd figure figcaption details
  summary table thead tbody tr th td button label input svg path circle line polyline rect
  g strong em small abbr br`.
- Every non-blank piece of text in `<body>` is inside a `data-qx` element; `data-qx`
  elements are never nested; each (role, key) pair appears once; every `id` is unique.
- `aria-label`, `placeholder`, `alt` and `title` attributes appear only on an element
  whose `data-qx-attr` names that attribute.
- `data-qx-from` appears only on the `figure` keyed `worst.ten_thousand_left`, as
  `10000`.
- Links (`<a href>`): on an asset page, `../`, `#{card id}`, and the page's source and
  identity URLs; on the landing page, `./`, `{id}/` for each asset, and the merged source
  URLs. `<link>` elements as in section 16.3.

### 16.8 Tests

`tests/golden/site_render.json` holds the cases: pages and landing pages with their
expected entries, and inputs that must fail with their messages. `tests/test_site_render.py`
reads each case, renders it, reads the result back (section 16.2) and compares the list
exactly; checks section 16.7 on every page it renders; checks that rendering twice gives
the same text and leaves the inputs unchanged; and checks that `HEADLINE_RULE_COUNT`
equals the number of distinct rule names in the `expected_rules` of
`tests/golden/headline.json`, so adding or removing a headline rule fails a test until
the site's number is updated.

### 16.9 The audit trail (Task 10d): `render_landing(index, pages, reviews)`

`render_landing` takes an optional third argument, `reviews`: the value of
`words/review_record.json`. Without it (`None`) the landing page is exactly as in section
16.5. With it, the record is checked first (`check_reviews`, below; after the existing
index and page checks), and the landing page gains openers and one hidden drawer per asset.
Asset pages are unchanged.

**The record.** `{"reviews": [review, …]}`, newest first. A review is `{"id", "title",
"reviewed_on" (YYYY-MM-DD), "data_as_of" (YYYY-MM), "reviewer", "assets"}`; `assets` maps
an asset id to its list of rounds; a round is exactly `{"round", "verdict", "text",
"reason", "control"}`. `verdict` is `approved`, `rejected` or `redrafted`. Only drafts that
passed the code checks of their day are recorded. Claude drafts the reasons on each
monthly review and Avi approves them; the newest review is added before
`scripts/build_site.py` runs.

**`check_reviews(reviews, index, pages)`** raises `SiteError` with the first problem, in
this order:

1. `reviews: unreadable`: not an object, or `reviews` is not a list with at least one item.
2. For each review in order (n = 1, 2, …): `reviews: <n>: unreadable` if it is not an
   object, `id`, `title` or `reviewer` is not non-empty text, `reviewed_on` is not a real
   date written `YYYY-MM-DD`, `data_as_of` is not `YYYY-MM` with a month from 01 to 12, or
   `assets` is not an object. Then `reviews: duplicate id <id>` if an earlier review has
   the same id.
3. `reviews: order`: each review's `data_as_of` must be later than the next one's.
4. For each review, for each asset in the record's order: `reviews: <id>: unknown asset
   <asset>` (not in the index); `reviews: <id>: <asset>: unreadable` (not a list, or a round
   that is not an object with exactly the five keys); `…: round numbers` (rounds are not
   numbered 1, 2, 3 … in order, as integers, never `true`/`false`); then for each round
   `…: round <n>: verdict` (not one of the three), `…: round <n>: text` (not non-empty
   text), `…: round <n>: reason` (an approval with a `reason` or `control` that is not
   `null`; a rejection or redraft whose `reason` is not non-empty text or whose `control`
   is neither `null` nor non-empty text); then `…: approved must be the last round` (an
   approval before the last round).
5. The newest review: `reviews: latest is not for <index data_as_of>` if its `data_as_of`
   differs from the index's. Then for each asset in index order: `reviews: <id>: missing
   <asset>` (not in it); `…: <asset>: headline not approved` (the page has a headline but
   its last round there is not an approval, or it has no rounds); `…: <asset>: approved
   without a headline` (an approval but no headline on the page); `…: <asset>: approved
   text differs from the headline` (the approved text is not exactly the headline's text).

This ties the published lines to the record: a refresh whose review was not recorded, or a
headline with no recorded approval, stops the site build.

**Openers** (buttons with `type="button"`, `aria-haspopup="dialog"` and
`data-trail="<asset id>"`; no `data-qx` on the button itself):

- Each slide's audit row (16.5 item 5) is inside its button, followed by `audit-open`, key
  the asset id: `Audit trail`.
- Gate `03` (16.5 item 6), after its text: a button holding `gate-open`, key `03`: `See
  the audit trail`, opening the **gate target**: the first asset in index order whose rounds
  in the newest review include a `rejected` one; if none, the first asset.

**Drawers**, after `</main>` and before the footer, in an element with the `hidden`
attribute holding, for each asset in index order, an element with `role="dialog"`,
`aria-modal="true"`, `id="trail-<asset id>"`, `aria-labelledby="trail-title-<asset id>"`
and the `hidden` attribute. In it, in order (key = the asset id unless stated; `<Mon
YYYY>` = the index's `data_as_of`; `{label}` = the index label):

1. `trail-label`: `Audit trail`.
2. `trail-title`, an `<h2>` with `id="trail-title-<asset id>"`: with a headline, `How
   {label}'s headline was made`; without, `Why {label} has no headline for <Mon YYYY>`.
3. `trail-close`: an empty button, `data-qx-attr="aria-label"`, `aria-label` `Close the
   audit trail`.
4. With a headline: `trail-status`: `Published · data to the end of <Mon YYYY>`;
   `trail-headline`: its text; then three steps, keys `<id>.1`, `<id>.2`, `<id>.3`:
   - `trail-step` `<id>.1`: `Drafted by {drafted_by}`; `trail-step-text` `<id>.1`: `It saw
     only figures from {label}'s own page and could cite only those. It cited {one|two} of
     them.` (the number of cited claims);
   - `trail-step` `<id>.2`: `Checked by code: {N} of {N} rules passed` (N =
     `HEADLINE_RULE_COUNT`); then one `trail-rule` per rule, keys `<id>.r01` to `<id>.r16`,
     in section 15.1 order: `Plain text, nothing blank` · `Cites 1 or 2 figures from its
     page` · `Only the investment's own past` · `One sentence, no questions` · `30 words or
     fewer` · `Every number is a cited figure` · `Figures exactly as the page shows` · `No
     advice words` · `No predictions` · `Numbers as figures, not words` · `No comparisons` ·
     `No ranking or loaded words` · `Names no other investment` · `A fall is called a fall`
     · `Recovery words match the facts` · `"in pounds" or "in dollars" said`;
   - `trail-step` `<id>.3`: `Reviewed by a person · approved {day of reviewed_on}`;
     `trail-step-text` `<id>.3`: `Read against {label}'s page. When next month's data
     arrives, this line comes down until a new one is reviewed.`
   Without a headline: `trail-status`: `Not published · data to the end of <Mon YYYY>`;
   `trail-none`: `No draft was approved for this data, so no line is shown until one
   passes review.`
5. `trail-earlier`, an `<h3>`: `Every draft, including the rejected ones`; `trail-note`:
   `Each passed the code checks of its day. Each verdict is a person's.`
6. For each review in record order that lists this asset (even with no rounds),
   `trail-review`, key `<id>.<review id>`: `{title} · reviewed by {reviewer}, {day of
   reviewed_on} · data to the end of {Mon YYYY of its data_as_of}`; then for each round,
   key `<id>.<review id>.<round>`: `trail-round`: `Round {n} · {Approved | Rejected |
   Redrafted, not used}`; `trail-draft`: its text; `trail-reason`: its reason, if not
   `null`; `trail-control`: `Now: {control}`, if not `null`.

`tests/golden/audit_trail.json` holds the cases (renders with their full read-back and
the `data-trail` values in document order, and the check's errors). Every rendered case
passes section 16.7, which allows `role`, `aria-modal`, `aria-labelledby`,
`aria-haspopup` and `data-trail` as above.

## 17. Writing the site's pages

`scripts/build_site.py` writes the HTML of section 16 into `site/`, and is the command Avi
runs after `scripts/build_pages.py`: `python3 scripts/build_site.py`. It is offline: no
network, no keys, no environment variables and no clock. It reads `site/data` and writes
only `site/index.html` and `site/<id>/index.html`. The same inputs always give
byte-identical files, so a run with nothing new shows no change in `git status`. It
imports only `json`, `os`, `pathlib`, `sys` and `web.render`.

### 17.1 `write_site(index, pages, out_dir, reviews=None)`

`index` is the value of `site/data/index.json`; `pages` maps each asset id to the value
of `site/data/<id>.json`. In order:

1. **Pages.** The ids are the `id` of each entry of `index["assets"]`, in order; if they
   can't be read (not a list, an entry that isn't an object, an id that isn't text) the
   run stops with `index: assets: unreadable`. Every id has an entry in `pages`, checked
   in index order (`<id>: page: missing`); then there is no other entry (`pages:
   unexpected <name>`, the first in alphabetical order).
2. **Output folder.** It must exist (`output folder: does not exist`); `write_site` never
   creates it. Apart from names starting with `.`, which are left alone, it may hold only:
   folders named `data` and `assets`, which are never read or changed; a file named
   `index.html`; and, for each id, a folder named with the id, which may hold only a file
   named `index.html` (and names starting with `.`). Anything else stops the run: another
   name, a file where a folder belongs or a folder where a file belongs, a leftover
   `.tmp`. The top level is checked first, naming the first such name in alphabetical
   order (`output folder: unexpected <name>`); then each id's folder, in index order
   (`output folder: unexpected <id>/<name>`). A removed asset's folder is deleted by hand
   (`git rm -r`), never silently.
3. **Render.** `render_landing(index, pages, reviews)` (sections 16.5 and 16.9; `reviews`
   is the fourth argument, `None` if not given), with the pages in index
   order; then `render_page(page, index)` (section 16.4) for each id in index order. A
   `SiteError` is reported as `site: render: SiteError: <message>`; any other error type
   is named alone (`site: render: RuntimeError`).
4. **Write, all or nothing.** First each id's folder that doesn't exist is created, in
   index order. Then each page goes to `<id>/index.html.tmp`, in index order, and the
   landing page to `index.html.tmp`, each written as its text encoded in UTF-8, with no
   newline translation. Every temporary file is then read back, decoded as UTF-8, and
   must equal (`==`) the text rendered for it, the pages in index order and then the
   landing page (`<file>: write: read back differently`). Only then is each file renamed
   into place, the pages in index order and `index.html` last. If anything fails before
   the first rename, every temporary file created and every folder this run created are
   removed, and the output folder is exactly as it was. `<file>` is `index.html` or
   `<id>/index.html`; any other failure while writing or reading back is `<file>: write:
   <ErrorType>`.
5. **Return** `{"data_as_of", "headlines", "written"}`: the index's `data_as_of`; the ids
   whose page has a headline (not null), in index order; and the files in the order they
   were renamed (`<id>/index.html` in index order, then `index.html`).

**Errors** are a `SiteWriteError`, defined in `scripts/build_site.py`, whose message is
exactly as above.

### 17.2 The command: `python3 scripts/build_site.py`

`main(argv, root, out)` returns the exit code and writes lines to `out`. It never prints
a traceback or a value.

- **Arguments:** none. Anything else prints `Usage: python3 scripts/build_site.py` and
  returns 2.
- **Loading**, each file read as UTF-8 with `json.load`: `root/site/data/index.json`
  (`FAILED: index: load: <ErrorType>`); then the ids, as in 17.1 step 1 (`FAILED: index:
  assets: unreadable`); then `root/site/data/<id>.json` for each id in order (`FAILED:
  <id>: load: <ErrorType>`); then `root/words/review_record.json` (`FAILED: reviews:
  load: <ErrorType>`). Each failure prints its line, then `Nothing was written.`, and
  returns 1.
- `write_site(index, pages, root/site, reviews)`. On success it prints `Pages for data as of
  <data_as_of>: <k> of <n> have an approved headline.` (`<n>` is the number of ids) and
  `Wrote <n + 1> files to site.`, and returns 0.
- On a `SiteWriteError`: `FAILED: <message>`. On anything else: `FAILED: unexpected
  <ErrorType>.` Either way, then `Check git status --short before committing anything.`,
  and exit code 1.

Each month, after the pages are built again with their headlines (section 15.4), and after
the month's review is added to `words/review_record.json` (section 16.9): run
`scripts/build_site.py`, then commit `site/data` and the site's HTML together.

## 18. Guided explanations (Task 11)

Each asset page carries, beside its cards, a fixed set of plain-English explanations:
one "in everyday terms" line and a few short panels per card. They are fixed templates
filled only with the page's own claim `display` values and dates: no new figure, no
rounding, no AI. Copy approved by Avi, 1 Oct 2026. The site shows them under each card as
a closed "Explain further" section; guided mode (Task 11b) steps through them.

### 18.1 `build_guided(page, facts)` (`words/guided.py`)

`page` is a built page (section 13.2); `facts` its asset's context entry without `why`
(`held_by_tracker`, `priced_in_pounds_holds_dollars`). Returns `{"steps": [step, …]}`, one
step per card in the page's card order, each `{"card": <card id>, "everyday": <text>,
"more": [{"title": <text>, "text": <text>}, …]}`. It never changes `page`. A card id not
listed below is a `WordsError`: `guided: unknown card <id>`.

Notation: `{x}` is claim `x`'s `display`; `{start x}` / `{end x}` its period's months as
`Mon YYYY`; **moved** `x` is `up {x}`, `down {x}` or `unchanged ({x})` by its direction;
**fx** `x` is `rose {x}`, `fell {x}` or `was unchanged ({x})`. A **dollar asset** has
claim `pound.local`. A panel marked *if …* is left out when any claim it names is missing
(never an error, never a placeholder). Titles are as written, in this order.

**bumpy** — everyday: `Two roads to the same town, one flat, one hilly. Volatility
measures the hills, not where the road ends up.`
1. *if `bumpy.volatility`*: `What goes in`: `One number for each month: how much a
   holding changed in pounds from one month-end to the next, with any income added back,
   from the end of {start bumpy.volatility} to the end of {end bumpy.volatility}.`
2. `How spread out they were`: `Volatility measures how far those monthly changes
   typically sat from their average, rises and falls alike. Bigger swings either way give
   a higher figure.`
3. `Why "a year"`: `The monthly spread is scaled to a yearly figure by multiplying it by
   the square root of 12. It is the usual convention, so investments can be compared on
   the same footing.`
4. *if `bumpy.tracker_volatility`* and the asset value `a` exists (`bumpy.volatility_common`
   if present, else `bumpy.volatility`): `Next to the tracker`: `Over the months both cover,
   from the end of {start bumpy.tracker_volatility} to the end of {end
   bumpy.tracker_volatility}: {a}, against {bumpy.tracker_volatility} for the
   developed-world tracker.`
5. `What it can't tell you`: `It treats a rise and a fall of the same size alike, and it
   says nothing about next month. A calm stretch can end suddenly.`

**worst** — everyday: `The deepest dip on a walk, measured from the highest point you'd
reached so far.`
1. *if `worst.months_to_low`, `worst.fall`*: `From high to low`: `{worst.months_to_low},
   from the end of {start worst.fall} to the end of {end worst.fall}.`
2. *if `worst.ten_thousand_left`, `worst.ten_thousand_lost`*: `In money`: `£10,000
   invested at that high would have been worth {worst.ten_thousand_left} at the low,
   {worst.ten_thousand_lost} less. That applies only to money put in at the high.`
3. *if `worst.months_to_recover`, `worst.months_underwater`*: `Getting back`: `It was back
   at that high by the end of {end worst.months_to_recover}: {worst.months_to_recover}
   after the low, {worst.months_underwater} after the high.` Otherwise *if
   `worst.below_high_at_end`, `worst.months_underwater`*: `Still below the high`: `It had
   not recovered by the end of {end worst.below_high_at_end}: still
   {worst.below_high_at_end} below its high, {worst.months_underwater} after it.`
4. `What month-ends hide`: `A fall that recovered within the same month doesn't show, so
   the worst moment may have been deeper.`

**panic** — everyday: `Three storms, and how it came out of each one, start to finish.`
1. `Three named periods`: `Global financial crisis: {g}. Covid crash: {c}. 2022 rate
   shock: {r}. In pounds, from the start to the end of each period.`, where each is
   **moved** `panic.gfc` / `panic.covid` / `panic.rate_shock`, or `not covered` when the
   claim is missing.
2. A dollar asset: the first window, in the order gfc, covid, rate_shock, that has all
   three of `pound.<w>.local`, `pound.<w>.currency`, `pound.<w>.gbp`: `Why the dollar
   matters here`: `Over the {global financial crisis | Covid crash | 2022 rate shock} it
   was {moved local} in dollars, and the dollar {fx currency} against the pound, so in
   pounds it was {moved gbp}. Step 5 shows how the two parts combine.` No such window: no
   panel. Not a dollar asset, with `priced_in_pounds_holds_dollars`: `Priced in pounds,
   holding dollars`: `It is priced in pounds, but what it holds is priced in dollars, so
   the exchange rate is already inside these figures.` Otherwise: `Priced in pounds`: `It
   is priced in pounds, so these figures have no separate exchange-rate part.`
3. `What start-to-end hides`: `Prices may have fallen further in between and partly
   recovered before the period ended.`

**next** — everyday: `Two friends' moods: near 1, when one is up the other usually is
too; near 0, one's mood tells you nothing about the other's.`
1. `What the number means`: `1 would mean always moving in step, 0 no pattern, and −1
   always opposite. It measures how consistently the monthly moves lined up, not how big
   they were.` (U+2212 minus.)
2. *if `next.rolling_lowest`, `next.rolling_highest`*: `It moves around`: `Over each
   36-month stretch it ranged from {next.rolling_lowest} (the 36 months to the end of {end
   next.rolling_lowest}) to {next.rolling_highest} (to the end of {end
   next.rolling_highest}).`
3. *if `next.mix_annualised`, `next.tracker_annualised`, `next.mix_volatility`,
   `next.tracker_volatility`*: `A 90/10 illustration`: `90% in the tracker and 10% in this
   investment, reset every December: {next.mix_annualised} a year against
   {next.tracker_annualised} for the tracker alone, with volatility of
   {next.mix_volatility} against {next.tracker_volatility}. An illustration, not a
   recommendation, before fees, trading costs and tax.`
4. `Not protection`: `A low figure does not mean it protects a portfolio: correlation says
   nothing about how big the moves were.`
5. *if `held_by_tracker` is true*: `You may already hold it`: `The tracker already holds
   these shares, so the 10% adds to a holding it already has.`

**pound** — a dollar asset: everyday `Buying something abroad: the price can change, and
so can the exchange rate. You feel both.`; panels `Two parts`: `What it did in dollars,
and what the dollar did against the pound. A UK holder gets both.`; *if `pound.local`,
`pound.currency`, `pound.gbp`*: `How they combine`: `Over the whole period: {moved
pound.local} in dollars, the dollar {fx pound.currency} against the pound, so {moved
pound.gbp} in pounds. The two parts multiply rather than add, so they never simply add
up.`; `It cuts both ways`: `When the pound rises against the dollar, a dollar holding
loses some of its gain for a UK holder.` Not a dollar asset, with
`priced_in_pounds_holds_dollars`: the same everyday line; `Hidden in the price`: `It is
priced in pounds, but what it holds is priced in dollars, so when the dollar moves against
the pound, its price in pounds moves too.`; `Why it isn't split out`: `With only a price
in pounds, the part that came from the exchange rate can't be separated out.` Otherwise:
everyday `Shopping at home: there is no exchange rate between you and the price.`;
`Nothing to split`: `It is priced in pounds, so a UK holder's figures have no separate
exchange-rate part.`

**limits** — everyday: `A rear-view mirror: it shows clearly where you've been, not
what's round the next bend.`; `The basis`: `Past results in pounds, measured at
month-ends, before platform fees, trading costs and tax.`; `Not a forecast`: `Past
behaviour does not predict future results. Nothing here says what to do.`

### 18.2 On the page (`render_page`)

A page may carry `guided` (pages written before Task 11 do not; without it the page is
exactly as in section 16.4). With it, `render_page` checks it first, after the existing
page checks: `<id>: guided: unreadable` unless it is an object with exactly the key
`steps`, a list of objects with exactly `card`, `everyday` (non-empty text) and `more` (a
list of 1 to 6 objects with exactly `title` and `text`, both non-empty text); then
`<id>: guided: cards differ` unless the steps' `card` values are the page's card ids in
order. Then, at the end of each card's section, after everything section 16.4 puts there:
a closed `<details>` whose `<summary>` holds `more-open`, key the card id: `Explain
further`; then `everyday-label`, key the card id: `In everyday terms`; `everyday`, key the
card id: the step's line; then for each panel *k* (1, 2, …), keys `<card id>.<k>`:
`more-number`: *k* as two digits (`01`), `more-title` (an `<h3>`): its title, `more-text`:
its text. `<details>`, `<summary>` and `<h3>` are already allowed by section 16.7.

**Guided mode controls (Task 11b).** With `guided`, the page also has, immediately
before the first card's section, a `<nav>` with the `hidden` attribute (the script shows
it) holding, in order: a button with `aria-pressed="false"` holding `mode-guided`:
`Guided`; a button with `aria-pressed="true"` holding `mode-full`: `Full page`; a button
holding `step-back`: `Back`; then for each step in order an empty button, role
`step-node`, key the card id, `data-step` the card id, `data-qx-attr="aria-label"`, whose
`aria-label` is `Step {k}: {card title}`, followed by `step-label`, key the card id: the
short label (`bumpy` `Bumpy`, `worst` `Worst fall`, `panic` `Panics`, `next` `Next to
tracker`, `pound` `The pound`, `limits` `Limits`); then a button holding `step-next`:
`Next`.

`tests/golden/guided.json` holds the cases: `build_guided` on the seven published Sep 2026
pages and on edited ones, and `render_page` with guided steps.
