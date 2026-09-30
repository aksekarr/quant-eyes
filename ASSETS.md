# Assets

Every font, icon, image or drawn asset the site uses, with its source and licence.
Avi picks each one from a shortlist; the pick is recorded here before any code uses it.
Changing an asset means changing its entry here and one Codex prompt.

## Display and figures font
- Asset: Sora
- Source: Fontsource, `@fontsource/sora` 5.3.0 (https://fontsource.org/fonts/sora)
- Licence: SIL Open Font License 1.1; attribution: none required; the licence file ships with the font files
- File: `site/assets/fonts/sora-latin-600-normal.woff2`, `sora-latin-700-normal.woff2` (latin subset); licence `site/assets/fonts/OFL-sora.txt`
- Used in: headings, card titles and the large figures
- Chosen: 2026-09-30 (shortlist of 7; checked on the font files for U+2212 minus, £ and equal-width digits)

## Body text font
- Asset: Atkinson Hyperlegible Next
- Source: Fontsource, `@fontsource/atkinson-hyperlegible-next` 5.3.0 (https://fontsource.org/fonts/atkinson-hyperlegible-next)
- Licence: SIL Open Font License 1.1; attribution: none required; the licence file ships with the font files
- File: `site/assets/fonts/atkinson-hyperlegible-next-latin-400-normal.woff2`, `-600-`, `-700-` (latin subset); licence `site/assets/fonts/OFL-atkinson-hyperlegible-next.txt`
- Used in: sentences, headlines and body text
- Chosen: 2026-09-30 (shortlist of 7; same checks)

## Labels font
- Asset: IBM Plex Mono
- Source: Fontsource, `@fontsource/ibm-plex-mono` 5.3.0 (https://fontsource.org/fonts/ibm-plex-mono)
- Licence: SIL Open Font License 1.1; attribution: none required; the licence file ships with the font files
- File: `site/assets/fonts/ibm-plex-mono-latin-400-normal.woff2`, `-500-` (latin subset); licence `site/assets/fonts/OFL-ibm-plex-mono.txt`
- Used in: small uppercase labels, tickers, provenance and data lines
- Chosen: 2026-09-30 (shortlist of 7; same checks)

Note: none of the three fonts' latin files has the square-root sign (U+221A) used once in
the volatility method text; browsers draw that one character from a system font.

## Icons
- Asset: Lucide icons `search`, `arrow-right`, `circle-alert`, `play`, `pause`, `sparkle`,
  `shield-check`, `user-check`, `chevron-left`, `chevron-down` (the Lucide versions of the
  icons on the approved design canvas)
- Source: Lucide, npm `lucide-static` 1.49.0 (https://lucide.dev)
- Licence: ISC; attribution: none required; licence file `site/assets/icons/LICENSE-lucide.txt`
- File: `site/assets/icons/<name>.svg`
- Used in: `docs/SITE-DESIGN.md`, Icons (drawn with CSS masks)
- Chosen: 2026-09-30 (with the design canvas)

## Site mark
- Asset: two overlapping circles (the investment and the tracker), beside the site name
- Source: Original, drawn by Claude on the design canvas, 30 Sept 2026
- Licence: original work for this project; attribution: none
- File: `site/assets/icons/mark.svg`
- Used in: the site header
- Chosen: 2026-09-30 (with the design canvas)

Files copied onto Avi's Mac by Claude's file bridge carry an embedded content-credentials
(`<metadata>`) block in the SVGs; it doesn't change how they draw.
