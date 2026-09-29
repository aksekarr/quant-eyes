# Verification log

Evidence that the published numbers are right, recorded as it is produced. Each entry
says what was checked, how, and what it showed. See BRIEF.md, "Evidence the build must
produce".

## 29 Sept 2026: first live run (data as of 2026-08)

**The run.** `python3 scripts/build_data.py`: 21 requests, 7 files written to
`data/derived/`. Month-ends per series: fx 229 (2007-08 to 2026-08), swda 200 (2010-01),
msft 440 (1990-01), aapl 440 (1990-01), nvda 332 (1999-01), sgln 184 (2011-05), iglt 236
(2007-01), azn 259 (2005-02), btc 141 (2014-12).

**Month-end rule caught a real data problem.** The first attempt stopped at
`swda: series: ProviderDataError: Month 2009-12 has a stale month-end date 2009-12-23`.
Alpha Vantage's first SWDA row is dated 23 Dec 2009, eight days before the London
market's last trading day of the year, so it is not a month-end value (METHODOLOGY 7.3).
SWDA now starts at Jan 2010 (DECISIONS, 29 Sept). A scan of all nine series (months and
dates only, no values) found no other stale month-end, bad value or gap.

**Output check.** Claude's separate checker read all seven files: exactly the expected
files; one as-of month; `check_document` passes on the files as read from disk; no list
outside the three stress windows; no text containing a query string, `apikey` or a token;
every number finite and in range (volatility 0 to 300%, correlations -1 to 1, returns
above -100%); start months as the 28 Sept data check predicted. Each file holds about 165
to 177 numbers, summarising 140 to 440 months.

**Dividend adjustment (Alpha Vantage adjusted close).**

| Line | Months with a dividend | Adjusted / unadjusted at first month |
|---|---|---|
| IGLT.LON | 40 of 237 (about two a year) | 0.616 |
| AZN.LON | 44 of 260 (about two a year) | 0.449 |

**External cross-check: IGLT against iShares.** Calendar-year total returns from our
adjusted series (month-end December to month-end December), against the fund returns
iShares publishes (product page, as of 25 Sept 2026):

| Year | Ours | iShares | Gap (points) |
|---|---|---|---|
| 2016 | +10.3% | +10.0% | +0.3 |
| 2017 | +1.4% | +1.7% | -0.3 |
| 2018 | +0.5% | +0.4% | +0.1 |
| 2019 | +6.7% | +6.8% | -0.1 |
| 2020 | +8.1% | +8.2% | -0.1 |
| 2021 | -5.0% | -5.2% | +0.2 |
| 2022 | -23.7% | -23.8% | +0.1 |
| 2023 | +3.6% | +3.7% | -0.1 |
| 2024 | -3.3% | -3.3% | -0.0 |
| 2025 | +4.7% | +5.1% | -0.4 |

Every year within 0.4 points, in both directions: the difference between the market
price we use and the fund's NAV. Missing coupons would show as a gap of roughly 1 to 3
points below in every year.

**Spot checks (approximate).** Claude compared several stress-window figures with the
underlying moves, from remembered market prices, not a formal source. For example,
bitcoin over the 2022 rate shock: about -55.7% in dollars, and the pound fell from 1.353
to 1.147 dollars (+18% for a dollar asset), so 0.443 x 1.18 = 0.523, a -47.7% return in
pounds, which is what the file shows. Apple over the financial crisis (-2.1%), and Nvidia
(+18.8%) and bitcoin (-27.0%) over the Covid crash, were consistent in the same way.

**Provider behaviour found.**
- Alpha Vantage names the monthly series `Monthly Adjusted Time Series`.
- Near its daily limit, Alpha Vantage answered `Invalid API call` twice before sending
  its rate-limit message; the same request worked on a fresh allowance.
- Alpha Vantage's rate-limit message writes the caller's API key into its text. The
  pipeline's cleaning (METHODOLOGY 9.5) replaced it with `[key]` before it was printed.

**Still open.** Whether Tiingo labels a daily crypto bar by the day it starts or ends
(METHODOLOGY 7.1). At most, it moves bitcoin's month-end by one day.
