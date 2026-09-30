# Site design: the look (Task 9c)

The approved design is on Avi's design canvas (30 Sept 2026). Its five boards are copied
into `docs/design/` as reference: `landing-desktop.html` (1440 wide),
`asset-desktop.html` (1440, the Microsoft page), `landing-phone.html` (390),
`asset-phone.html` (390) and `not-covered-phone.html` (390). They are a design tool's
files: they use its template syntax (`{{…}}`), inline styles, Google Fonts links and a
script of their own. Read them for layout, spacing, colour and type; never copy their
fonts links, scripts, template syntax or placeholder text into the site.

**Where this file and the boards differ, the boards win** (they are what Avi approved),
except for the rules: text, order and sizes as section 16 fixes them; sizes only from
`--qx-size`; `hidden` stays hidden; no JavaScript, no animation, no external URLs, no red
or green.

Task 9c is the **static look** only. No JavaScript and no animation: motion and
interaction (count-ups, the border sweep, the headline pass, search, the phone
accordions) are Task 9d. Without JavaScript, every page must still read well: the
landing page shows all the headlines as a list, and elements with the `hidden`
attribute stay hidden.

## Files

- `site/assets/site.css`: the only stylesheet (new).
- `site/assets/fonts/` and `site/assets/icons/`: provided and recorded in `ASSETS.md`.
  Never edit, add or remove a file in them.
- `web/render.py`: markup only. Add wrappers, element choices and class names wherever
  the layout needs them. Every text, order and size stays exactly as section 16 fixes it:
  `tests/test_site_render.py` and `tests/test_build_site.py` must pass unchanged, and
  section 16.7 still holds (no inline style except sizes, no new text, no inline SVG, no
  `<img>`).
- `tests/test_site_look.py`: the checks below (new).

## Type

`@font-face` for every file in `site/assets/fonts/`, `font-display: swap`,
`url("fonts/<file>") format("woff2")`, with the family names `Sora`, `Atkinson
Hyperlegible Next` and `IBM Plex Mono` and the weight in the file name.

- **Sora** (600, 700): the site name, the landing heading, card titles, the asset name,
  the headline text (as the boards set it) and every large figure (`figure`,
  `scale-value`, `bar-value`).
- **Atkinson Hyperlegible Next** (400, 600, 700): sentences and other text.
- **IBM Plex Mono** (400, 500): small labels (kicker, tags, section labels, chain,
  card numbers, maths heads, footer data), usually upper case with letter spacing, as
  on the canvas.
- Every figure and table value uses `font-variant-numeric: tabular-nums`, so a count-up
  in 9d never jitters.

## Colour and surfaces

Take the exact values from the canvas: ground `#050A1C` with its soft radial glows and
masked dot grid; text `#EEF2FF`; secondary text `#B6C1E2`; labels `#A9B6E0`; muted
`#8E9AC2`; accent ice `#86CCFF` (the canvas default); glass cards (white at about 4.5%
fading to 1.5%, a 9% white border, a soft glow shadow); focus ring 2px `#9AD4FF`,
offset 3px. **No red and no green anywhere**, and up or down is never shown by colour:
the words carry direction.

## Icons

Decorative only, drawn with CSS masks from `site/assets/icons/` (`mask`/`-webkit-mask`
with `url("icons/<name>.svg")` and `background-color: currentColor`), on pseudo-elements
or empty decorative elements, never as `<img>` or inline SVG. Where each goes, as on the
canvas: `mark` beside the site name; `chevron-left` on the back link; `search` in the
search field; `circle-alert` on "Not covered yet"; `sparkle`, `shield-check` and
`user-check` on the three steps of the provenance chain; `pause` and `play` on the
headline control; `arrow-right` on "Open …" and the tiles; `chevron-down` on "Show the
maths".

## Visuals

Every length and position comes only from the `--qx-size` of its `size` element (for
example `width: calc(var(--qx-size) * 100%)`), on a track that starts at zero and runs
the full width, so what the eye compares is the true ratio.

- Volatility bars: two bars on identical tracks, asset and tracker.
- The £10,000 bar: a full track for £10,000 with the part left filled to `worst.drain`.
- The timeline: the fall and the recovery (or the time since the low) as two segments
  whose lengths are their sizes: horizontal with the points beneath on desktop, vertical
  with the labels beside on phone, as the boards draw them.
- The correlation scale: a track from −1 to 1, the range band from `next.range-low` to
  `next.range-high`, and the marker at `next.correlation`.
- The 90/10 bar: two parts, 90 and 10.

Straight shapes only. Nothing that looks like a price line or chart.

## Layout

- **Desktop** (1024px and wider): as the desktop boards. On the landing page, the heading,
  tagline and search sit on the left and the headlines card on the right, with the tiles
  as a full-width row below both. On an asset page, the questions sit in a sticky rail
  beside the cards, and each card leads with its large figure, with the sentence under
  it and the visual beside or below, as drawn.
- **Phone** (below 640px): as the phone boards: one column, the questions as a
  horizontal row of pills, cards stacked, touch targets at least 44px.
- In between: a sensible blend. No horizontal scrolling at 360px wide.
- `details[open]` swaps "Show the maths" for "Hide the maths" in CSS (the `hidden`
  attribute on `maths-hide` may be overridden for that one case). Any other element with
  `hidden` stays hidden.
- Hover and focus may react (lift, glow, border brighten) with transitions of 200ms or
  less. `@media (prefers-reduced-motion: reduce)` turns every transition off.

## Accessibility

Text contrast at least 4.5:1 against its background (3:1 at 24px and above); a visible
focus ring on every link, button and summary; the reading order is the HTML order (CSS
may place things side by side, but never reorders text in a way that changes its
meaning).

## Checks (`tests/test_site_look.py`)

- `site/assets/site.css` exists and contains none of: `http:`, `https:`, `//` at the
  start of a `url(`, `@import`, `@keyframes`, `animation`, `infinite`, `javascript:`,
  `expression(`.
- Every `url(...)` in it is relative and names a file that exists under `site/assets/`.
- There is an `@font-face` for every file in `site/assets/fonts/` ending in `.woff2`, and
  the three family names appear.
- It has a `@media (prefers-reduced-motion: reduce)` block.
- No red or green: every colour written in it as hex, `rgb()`/`rgba()` or `hsl()`/`hsla()`
  is converted to HSL, and none with saturation of at least 40% and lightness from 20% to
  80% has a hue from 0 to 20, 90 to 160, or 340 to 360 degrees.
- Every page that `render_page` and `render_landing` produce for the golden cases in
  `tests/golden/site_render.json` links only `assets/site.css` (landing) or
  `../assets/site.css` (asset pages) as its stylesheet.
