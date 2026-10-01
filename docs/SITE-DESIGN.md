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
  Never edit, add or remove a file in them (the one exception: Task 10b removes
  `icons/mark.svg`).
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

## Header logo (Task 10b)

The site name is drawn as the Quant Eyes logotype, `site/assets/brand/logo.svg` (ASSETS.md),
as a CSS background on the `site-name` link: about 40px high on wider screens and 30px at
639px and below (enlarged in Task 10f from 28px and 24px), keeping its proportions (5475 × 1142). The link's text, `Quant Eyes`, stays
in the page for screen readers and the read-back, moved out of view with `overflow: hidden`,
`white-space: nowrap` and `text-indent: 100%`; never `display: none`, `visibility: hidden`,
`font-size: 0` or a `content` replacement. The link keeps a 44px touch target. No tile and
no `::before`/`::after` on the site name. `site/assets/brand/` is provided: never edit, add
or remove a file in it. The favicon is `site/assets/brand/favicon.svg` (METHODOLOGY 16.3).
`site/assets/icons/mark.svg` is retired in Task 10b.

## Landing v2 (Task 10c)

As on the design canvas (artboard ProofLanding, approved 30 Sept 2026). Words and order are
fixed by METHODOLOGY 16.5; this is the look.

- **Top:** the same two columns as now: intro (kicker, hero, tagline, search) on the left,
  the "In one line" headline card on the right. The hero (`What am I actually getting into?`, Task 10g) has the
  gradient on `actually` only (a `span` with `data-layout="hero-accent"`).
- **Audit row** (inside each slide, under the headline): one rounded chip row, min-height
  48px, padding 10px 14px, radius 14px, border `rgba(134, 204, 255, 0.30)`, background
  `rgba(134, 204, 255, 0.07)`, 14px semibold `#DCE3F7`. Three steps, each with its icon
  as a CSS mask (`sparkle`, `shield-check`, `user-check`, as the asset page's chain), and a
  decorative `→` between steps in `#6F7BA6`, drawn with CSS (`::before`/`::after` with
  `content: "→"` is allowed here), never as page text. It wraps on narrow screens. It may
  reuse the chain's light-up motion (`data-layout="chain"`) if that needs no new script.
- **Gates** (full width, under the top two columns, above the tiles), margin-top about
  44px: `gates-title` as a small mono label (12px, 500, 0.14em, `#A9B6E0`); then three
  cards in a grid `1fr 1fr 1.25fr`, gap 14px; each card padding 20px 22px, radius 20px,
  border `rgba(255, 255, 255, 0.12)`, background `rgba(255, 255, 255, 0.035)`; number in
  mono 12px accent, title in Sora 19px 600 on the same line, text 15px/1.5 `#B6C1E2`. Gate
  03 is highlighted: border `rgba(134, 204, 255, 0.35)`, background
  `linear-gradient(160deg, rgba(134, 204, 255, 0.12), rgba(134, 204, 255, 0.03))`, text
  `#DCE3F7`, its `strong` white. At 1023px and below the cards stack in one column.
- Remove the rules for roles the landing page no longer has (`strip`, `slide-meta`) and any
  landing-only `chain` placement; keep everything the asset pages use.
- No new colours outside this list and the existing palette; no red or green.

## Audit trail drawer (Task 10d-2)

The drawers and openers are built by `render_landing` (METHODOLOGY 16.9). This task makes
them work and look as on the design canvas (artboard ProofDrawer). Script and styles only.

**Look.**
- The drawers' outer container (the element with `hidden` that holds them) becomes the
  backdrop when open: fixed to the viewport, full size, `rgba(3, 6, 18, 0.72)`, above
  everything else.
- The open drawer is a panel fixed to the right edge, full height, width
  `min(520px, 100vw)`, background `#0B1230` with a 1px left border
  `rgba(255, 255, 255, 0.10)` and the existing card glow; padding 28px 28px 40px; it
  scrolls inside itself (`overflow-y: auto`, `overscroll-behavior: contain`). At 639px and
  below it is the full screen width, padding 20px.
- `trail-label` as a small mono label; `trail-title` in Sora 24px 600; `trail-close` a
  44px square button in the top right corner with an X drawn in CSS (two 18px bars on
  `::before`/`::after`, rotated 45 degrees, `currentColor`; no new icon file).
- `trail-status` as a small mono label; `trail-headline` in a block like the landing
  headline card (Sora 20px). The three steps as a numbered list with the accent numbers;
  the 16 `trail-rule` items as a two-column list (one column at 639px and below), each
  with the `shield-check` mask in the accent colour. `trail-none` in the secondary colour.
- `trail-earlier` as a small mono label above the rounds; `trail-note` muted. Each
  `trail-review` as a mono label; each round a card (radius 14px, border
  `rgba(255, 255, 255, 0.10)`): `trail-round` mono, `trail-draft` in body text 16px,
  `trail-reason` secondary 14px, `trail-control` 14px semibold in `#DCE3F7`. A rejected
  round's draft has a 1px line through it in `rgba(238, 242, 255, 0.45)`
  (`text-decoration: line-through`), chosen from the round's `Rejected` text by a
  `data-verdict` attribute that `render_landing` may add to the round's wrapper
  (`approved`, `rejected`, `redrafted`; markup only, no new text).
- The openers: the audit row stays as styled in 10c, now as a button (keep its look,
  `cursor: pointer`, the hover lift from the existing interaction rules, a visible focus
  ring), with `audit-open` pushed to the right as a small mono label with the
  `arrow-right` mask. `gate-open` as a small mono accent label under gate 03's text.

**Behaviour** (`site/assets/site.js`):
- Clicking an opener (`[data-trail]`) opens the drawer `#trail-<value>`: remove `hidden`
  from the container and that drawer (every other drawer stays hidden), set `inert` on
  `body > header`, `main` and `footer`, stop the page scrolling behind
  (`overflow: hidden` on `html` via a class), move focus to the drawer's `trail-close`.
- Closing: the close button, `Escape`, or a click on the backdrop outside the panel.
  Hide the drawer and the container, remove `inert` and the scroll lock, return focus to
  the opener that opened it (or to the site name when it was opened from the address).
- While open, `Tab` and `Shift+Tab` cycle within the drawer.
- The headline carousel pauses while a drawer is open and resumes on close only if it was
  playing before.
- **Links:** on load, and on `hashchange`, if the address ends `#trail-<id>` and that
  drawer exists, open it. Opening sets the address to `#trail-<id>` and closing removes
  the hash, both with `history.replaceState` (no new Back-button entries). Any other hash
  is left alone.
- Motion, only under `prefers-reduced-motion: no-preference`: the backdrop fades in and
  the panel slides in from the right over 240ms, once; closing is immediate. With reduced
  motion it simply appears.
- Without JavaScript the drawers stay hidden and the page reads as before.
- The script rules above still hold. In addition it may set and remove `inert`, call
  `history.replaceState`, read `location.hash` and listen for `hashchange` and `keydown`
  (on the open drawer only). It never changes any `data-qx` text.

## Explain further (Task 11a)

The closed `<details>` at the end of each card (METHODOLOGY 18.2), styled like "Show the
maths": a full-width summary row, 44px minimum, accent text `Explain further` with the
`chevron-down` mask turning when open. Inside: `everyday-label` as a small mono label,
`everyday` in 17px italic-free body text in `#DCE3F7` inside a soft accent block
(`rgba(134, 204, 255, 0.07)` background, radius 14px, padding 14px 16px); then the panels
in a grid `repeat(auto-fill, minmax(240px, 1fr))`, gap 12px, each a card (radius 16px,
border `rgba(255, 255, 255, 0.10)`, background `rgba(255, 255, 255, 0.03)`, padding 16px
18px) with `more-number` mono accent 12px, `more-title` Sora 17px 600, `more-text` 15px
`#B6C1E2`. One column at 639px and below. Closed by default on every page; no script
needed. Guided mode (Task 11b) reuses these sections.

## Guided mode (Task 11b)

As on the design canvas (artboards GuidedDesk and GuidedPhone, approved 1 Oct 2026). Script
and styles only; every word is already in the page (METHODOLOGY 18.2).

- The full page stays the default and the no-script page. The script shows the guided
  `<nav>`; `Guided` / `Full page` switch modes (update `aria-pressed`). The choice is
  remembered only in the address: guided mode sets `#guided` (and `#guided-<card id>` for
  the current step) with `history.replaceState`; loading with either opens guided mode
  there. No storage.
- Guided mode shows one card section at a time (the others get `hidden`), the headline
  card and rail are hidden, and the `<nav>` sits directly under the current card: Back,
  the track of step nodes joined by a line (current node filled accent with glow, visited
  nodes dim accent, labels under nodes on wide screens, labels hidden at 639px and below
  with the current one shown), Next. Back is `aria-disabled` on the first step, Next on
  the last. Clicking a node jumps there. Moving to a step closes that card's
  `Explain further`, scrolls the card's top into view and moves focus to its title
  (`tabindex="-1"`).
- In guided mode each card's `Explain further` summary becomes the centred pill from the
  board, under the track; its panels open below.
- Keyboard: Left/Right arrows move between steps when focus is on the track. Everything is
  reachable by Tab; touch targets at least 44px.
- Motion only under `prefers-reduced-motion: no-preference`: the new card fades/rises in
  once (300ms). Full page mode is exactly today's page.
- The script rules (Motion and interaction) still hold; it may also set `hidden`,
  `tabindex`, `aria-disabled`, `aria-pressed`, `aria-current` and use
  `history.replaceState` and `location.hash` as here and in the audit trail.

## Nudges (Task 10h)

- **Hint:** about 1.2s after the landing page loads (and only if no drawer is open from the
  address), the script shows the hint: a small pill anchored just below the current
  slide's audit row, pointing up at it with a small CSS caret, in the page's look (card
  gradient, 1px `rgba(134, 204, 255, 0.35)` border, the accent glow, mono 12px uppercase
  label like `audit-open`, the `arrow-right` mask). `hint-open` opens the current slide's
  audit trail exactly as its audit row does; `hint-close` is a 32px circle with a CSS X.
  It hides for good (this page view) on its own close, on opening any drawer, on any
  click elsewhere, on scroll past 200px, and on any key press. It never covers the audit
  row, Open button or controls; at 639px and below it sits full width under the audit row.
  It must not move focus or steal it, and is not announced as an alert.
- **Motion** (only under `prefers-reduced-motion: no-preference`): the hint rises 8px and
  fades in over 300ms with the same easing as the page's other motion, plus one soft
  accent glow pulse (the existing chain light-up style), once. No looping, no bounce.
  With reduced motion it simply appears.
- **Drawer link:** `trail-guided` sits at the end of each drawer as a full-width
  accent-outlined button (like the Explain further pill) with the `arrow-right` mask.
- No storage: the hint shows once per page view.

## Icons

Decorative only, drawn with CSS masks from `site/assets/icons/` (`mask`/`-webkit-mask`
with `url("icons/<name>.svg")` and `background-color: currentColor`), on pseudo-elements
or empty decorative elements, never as `<img>` or inline SVG. Where each goes, as on the
canvas: `chevron-left` on the back link; `search` in the
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
  start of a `url(`, `@import`, `infinite`, `javascript:`, `expression(`. (Task 9c also
  banned `@keyframes` and `animation`; Task 9d allows them under the motion rules below.)
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

# Motion and interaction (Task 9d)

Everything that can react does, and every movement **lands on the exact checked figure
or the static layout and stops**. Nothing loops, nothing suggests live data (no ticker
tape, no pulsing "live" dots, no red or green, no price lines), and the page without
JavaScript, or with reduced motion, is already the finished page.

## Files

- `site/assets/site.js` (new, the only script): plain JavaScript, no libraries, no
  modules, loaded with `defer` as the head already does.
- `site/assets/site.css`: motion styles may be added. `@keyframes` are allowed; every
  animation runs once (no `infinite`, and any `animation-iteration-count` is `1`); every
  animation and transition sits inside `@media (prefers-reduced-motion: no-preference)`
  or is switched off by the reduced-motion block.
- `web/render.py`: markup hooks only (attributes, wrappers, element choices), with every
  text, order and size exactly as section 16 fixes them, and section 16.7 holding.
- `tests/test_site_look.py`: amend its checks as described above; `tests/test_site_motion.py`
  (new): the checks at the end of this section.

## Rules for the script

- It never fetches anything: no `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`,
  `import(`, `navigator.sendBeacon`. No `eval`, `new Function`, `document.write`,
  `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `setInterval`, `localStorage` or
  `sessionStorage`.
- It never changes the text of a `data-qx` element. The only text it ever writes is the
  passing digits of a count-up, into an element it creates with `aria-hidden="true"`
  inside the figure while the figure's own text is visually hidden (never removed), and it
  removes that element when the count ends, leaving the figure exactly as built.
- It may add and remove classes, `hidden`, `aria-*` states (`aria-expanded`,
  `aria-current`, `aria-pressed`) and CSS custom properties.
- If `window.matchMedia("(prefers-reduced-motion: reduce)")` matches, nothing moves:
  everything shows its final state at once, and the headlines don't advance by themselves.
- Motion starts when its element is at least half in view (`IntersectionObserver`), runs
  once, and never replays on scrolling back, except the hover replay of the border sweep.
- If anything in the script fails, the page must still read exactly as the static page.

## What moves

- **Count-ups.** Each `figure` element counts once from 0 (or from its `data-qx-from`,
  for the £10,000 bar, counting down) to its own value, in about 1.2 seconds with an
  ease-out. The value is read from the figure's own text: an optional true minus sign
  (U+2212), an optional `£`, digits with thousands commas, optional decimals and an
  optional `%`. Every passing frame uses the same format as the final text (same decimals,
  commas, `£`, `%`, minus sign), and the last frame is the figure's own text. A figure
  whose text doesn't match that pattern doesn't count. `scale-value` doesn't count; the
  correlation marker slides instead.
- **Visuals** grow once from zero to their size when their card comes into view: the
  bars, the £10,000 fill (falling from full to what was left, in step with the count),
  the timeline segments (the fall, then the recovery or the time since the low), the
  correlation marker (sliding from the middle of the scale to its place, with the range
  band fading in), and the 90/10 parts. When they stop, every size element's box is
  exactly where the static page puts it.
- **Border sweep.** The headline card on an asset page and the headlines card on the
  landing page: a bright arc travels once around the border when the card comes into
  view (about 1.6 seconds), then the border rests as the still glow. On devices with a
  fine pointer, hovering replays one sweep.
- **Provenance chain.** Its three steps light up in turn, once, when it comes into view.
- **Hover and focus** (fine pointer only): tiles and cards lift slightly, and a soft
  spotlight follows the pointer over them (CSS custom properties set from the pointer
  position). Keyboard focus shows the focus ring.

## Interaction

- **Landing headlines.** With JavaScript, the headlines card shows one headline at a time
  (the others get `hidden`) and its controls are shown. Each headline stays 6 seconds,
  with its segment button filling as a progress bar; after the last, the card returns to
  the first and stops: one pass only. A click, tap or keyboard focus anywhere in the card
  stops the automatic advance for good. A segment button shows its headline
  (`aria-pressed` on the current one). The pause button pauses, and its `play` label
  replaces `pause`; play continues the pass from the current headline, to the end, then
  stops on the first. With reduced motion there is no automatic advance: the first
  headline shows, and the segment buttons work. The slides are not announced as they
  change.
- **Search.** JavaScript shows the search. Typing filters the results by label, ticker or
  name, ignoring case (the text already in each result); an empty field shows no results;
  text that matches nothing shows the "Not covered yet" block. Enter goes to the first
  result shown. The tiles below stay as they are.
- **Questions rail.** The card most in view marks its rail link with `aria-current="true"`;
  on phones the pill row scrolls to keep it visible. The links jump to their cards
  (smoothly, unless reduced motion).
- **Phone accordions** (below 640px only): the `next` and `pound` cards start collapsed to
  their number and title, and the title becomes the toggle (a `<button>` inside the `<h2>`
  with `aria-expanded`). The `limits` card never collapses: the risk wording always shows.
  On wider screens nothing collapses.
- "Show the maths" stays the native `<details>` toggle.

## Checks (`tests/test_site_motion.py`)

- `site/assets/site.js` exists and contains none of the banned names above.
- `site/assets/site.css` contains no `infinite`, and every `animation-iteration-count` in
  it is `1`; it has a `@media (prefers-reduced-motion: reduce)` block.
- Every page rendered for the golden cases still links `assets/site.js` (or
  `../assets/site.js`) as its only script, with `defer`.

Claude also checks the pages in a headless browser: with and without JavaScript, and with
reduced motion; that once motion ends every `data-qx` element's text equals the built
HTML and every size element's box equals the static page's; that nothing is still
animating; that the headlines stop after one pass and on interaction; the search; and that
no request leaves the site.
