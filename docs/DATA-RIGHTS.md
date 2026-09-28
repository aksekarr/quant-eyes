# Data rights

Findings as of 28 Sept 2026. Terms change: re-check before any public release.
This is a product assessment, not legal advice.

## Rules that apply to every source

- Raw provider data is held in memory only, never written to disk, committed or logged.
- Only derived statistics are published. No price series, no rebased growth lines, no
  output that could reasonably be used to reconstruct the underlying data.
- Every source is attributed on the site with a "data as of" date.
- JSON served to a browser is downloadable, so everything published must itself be
  permissible to publish. Keeping the link unlisted does not change that.
- Before public release, ask the chosen provider to confirm: retention, the actual
  displayed outputs, and sending derived figures to an AI provider.

## Sources

| Source | What it could supply | Terms (summary) | Status |
|---|---|---|---|
| Tiingo (free/Starter) | US stocks, US ETFs, crypto, FX | Starter plans may not store data; processing must be transient in memory. Derived products (e.g. volatility, averages, percentage returns, Sharpe) may be distributed if they cannot substitute for or reconstruct the data. Coverage of London-listed funds unconfirmed. | Candidate, test in data check |
| Alpha Vantage (free) | US and London stocks/ETFs (.LON), FX, crypto | Non-commercial licence covering "investment analysis, research"; public display not explicitly addressed. Some endpoints premium. About 25 requests a day on free. | Candidate, test in data check |
| Bank of England Database | Gilt yields, Bank Rate | Open Government Licence v3.0, attribution required. Some exchange-rate series excluded (third-party licensed); check series before use. | Usable for macro context |
| FRED | US government series | Required notice: "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis." Third-party series need the owner's permission (e.g. Coinbase BTC prohibits reproduction). Terms reportedly include AI-related restrictions; clarify before use. | Not planned for v1 |
| ECB | Euro FX reference rates | Reportedly allows reuse with attribution and clearly identified modifications (from an external review, not yet checked). | Possible currency source, unverified |
| LBMA / benchmark gold | Spot gold history | Actively licensed; historical data removed from the World Gold Council site at ICE Benchmark Administration's request (2025). | Excluded |
| CoinGecko (free) | Crypto | Attribution required, non-commercial, about 1 year of daily history. | Too short |
| Stooq | Broad free CSVs | No clear terms found. | Not used |

## Sources

- Tiingo terms: https://app.tiingo.com/tos/ (section 1.6)
- Alpha Vantage terms: https://www.alphavantage.co/terms_of_service/
- Bank of England legal: https://www.bankofengland.co.uk/legal
- FRED API terms: https://fred.stlouisfed.org/docs/api/terms_of_use.html
- World Gold Council gold prices: https://www.gold.org/goldhub/data/gold-prices
- CoinGecko API pricing: https://www.coingecko.com/en/api/pricing
