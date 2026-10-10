# Design for standalone graphics

Composition rules for README cards, banners, diagrams, loaders and badges: what to show, on what grid, in which colors and type, and how much may move.

## 1. Mechanism over decoration

- Show what the thing does, in its own nouns: input, processing, output. Read the code or the user's description for the real stages; renaming labels on a generic scene does not make it accurate.
- Every moving element means something: a packet is a request or an artifact, a line draw is progress or time, a pulse is live status, a highlight is the active step. If an element moves and means nothing, cut it or demote it to ambient texture.
- One idea per graphic. A card that explains the build pipeline does not also show stars and languages.
- No numbers that read as claims unless they come from real data. Placeholder metrics in a public README become claims.
- Labels in diagrams: at most about 4, uppercase mono, 12 characters or fewer, no sentences. Prose belongs in the README text next to the image.

## 2. Canvas and layout grid

| Piece | Size (px) | Notes |
| --- | --- | --- |
| full-width card, hero | 840 x 112 to 840 x 250 | 840 fits a desktop README column at about 1:1 |
| section header | 840 x 64 | eyebrow + title + rule; transparent, needs a light variant |
| divider | 840 x 14 | transparent; keep the line neutral |
| half card | 410 x 196 to 410 x 262 | two side by side with a 20 px gap; they wrap on phones |
| third card | 270 x 150 | three per row with 15 px gaps |
| marquee strip | 840 x 80 per row | 44 px icons, 14 px gaps |
| badge, pill | height 20-28 | radius = height / 2 |
| loader, icon | 24 to 96 square | `viewBox` sized so the shape scales cleanly |

- Always set `width`, `height` and `viewBox="0 0 W H"` together so the file scales down without clipping.
- Card frame: `<rect x="0.5" y="0.5" width="W-1" height="H-1" rx="14">` puts a 1 px stroke on whole pixels. Radius 14-18 for outer cards, 10-12 for tiles, 4-8 for diagram panels.
- Tile grid: `tile_w = (W - 2 * pad - (cols - 1) * gap) / cols` with `pad` 16 and `gap` 10-12. Four tiles on 840 with a 12 px gap give (840 - 32 - 36) / 4 = 193 px each.
- Inner padding 18-24 px. Eyebrow (small uppercase mono) near y 28-34, title baseline 20-30 px below it.
- Phones: an 840 px card on a 375 px phone renders at about 0.41x (343 / 840). A 24 px label lands near 10 px; 9 px text becomes texture. Whatever must be read on a phone is at least 22-24 px drawn on an 840 canvas, or the piece uses a narrower canvas.

## 3. Palette: one accent plus neutrals

- One accent family: a light shade for ink and lines, a deep shade for fills. Derive the deep shade by one rule and use it everywhere (for example HLS lightness minus 0.15 and saturation times 0.9). Two different derivations in one project produce near-miss colors.
- Semantic colors keep one meaning: green only for live or ok, amber only for warning, red only for failure.
- Tints through 8-digit hex alpha on the accent: `14` (about 8%) for fills, `22`-`30` for active fills, `55` for chip borders, `cc` for strong strokes. Expand a 3-digit accent (`#abc` to `#aabbcc`) before appending alpha; `#abc14` is invalid.
- Neutrals as an alpha ladder of white on dark (or near-black on light): 3% panel fill, 8-12% borders and rules, 35-50% secondary text, 70-85% body text, solid `#f3f4f6` for primary text. The light variant mirrors it with `rgba(11,16,18,a)`.
- Avoid gradient text, glow and blur filters: filters are expensive to repaint on every frame and blur the edges that make small text legible.

### Colors on both GitHub themes

Anything transparent sits on GitHub's background: `#ffffff` (light) or `#0d1117` (dark) in the default themes (dimmed and high-contrast themes differ). Graphics need 3:1 against it (WCAG 1.4.11, https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html); body text needs 4.5:1. Ratios computed with the WCAG relative-luminance formula:

| Color | vs `#ffffff` | vs `#0d1117` | On a transparent file |
| --- | --- | --- | --- |
| `#60a5fa` blue 400 | 2.54 | 7.44 | dark theme only |
| `#38bdf8` sky | 2.14 | 8.83 | dark theme only |
| `#22c55e` green | 2.28 | 8.31 | dark theme only |
| `#f59e0b` amber | 2.15 | 8.81 | dark theme only |
| `#2563eb` blue 600 | 5.17 | 3.66 | graphics on both |
| `#1f6feb` | 4.63 | 4.08 | graphics on both |
| `#3b82f6` blue 500 | 3.68 | 5.15 | graphics on both |
| `#a855f7` purple | 3.96 | 4.78 | graphics on both |
| `#2da44e` green | 3.22 | 5.89 | graphics on both |
| `#797979` gray | 4.35 | 4.35 | the best single gray; large text and graphics on both |
| `rgba(127,127,127,0.28)` | 1.38 | 1.43 | decorative hairlines only |

No single color reaches 4.5:1 on both backgrounds (the best gray tops out at 4.35:1), so body text on a transparent file needs a `<picture>` pair or an opaque card behind it. Pale accents that sing on dark (blue 400, sky, green, amber) disappear on light: that is the "pale text vanished in light mode" failure.

## 4. Typography

- System stacks only (no web fonts load inside an image):
  - sans: `-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif`
  - mono: `ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace`
  - Inside a double-quoted attribute, quote family names with single quotes. Declaring the stack once in a `<style>` class (`.m { font-family: ... }`) keeps files small.
- Width estimates (no text measurement is available when generating):
  - Per-character advance as a fraction of the font size, as `forge.py` estimates it (rounded up so text runs a little wide): mono 0.62, sans 0.56, bold sans (800, digits and mixed case) 0.6, sans uppercase 0.7. Add `letter-spacing` per character on top (forge's mono class uses 1.2 px).
  - Shipped hand-tuned values agree: 9 px mono chips with 1 px spacing at 6.2 px per character, 10 px pills at 7.1, 14 px terminal text at 8.4 (0.6 em).
  - These are estimates; the fallback font differs per OS, so leave about 10% slack and shrink or truncate with `...` past it.
  - Hard fit as a last resort: `textLength="180" lengthAdjust="spacingAndGlyphs"` forces an exact width at the cost of squeezed glyphs.
- SVG collapses runs of spaces. Position separate `<tspan>` or `<text>` pieces with their own `x`, or use `xml:space="preserve"` (deprecated in SVG 2, still honored).
- Hierarchy with size and weight, not color count: eyebrow 9-11 px uppercase mono with 1.2-2 px spacing, title 19-26 px sans 700-800, body 11-13 px sans 500, numbers 22-30 px sans 800.

## 5. Depth in three layers

1. Back: texture at very low contrast (a 24 px grid pattern at 3.5% white, dots, rails).
2. Middle: panels with a 1 px border at 8-12% and a 3% fill; opaque where wires pass under them.
3. Front: packets, pips, highlights and labels. Nothing decorative ever sits on top of text.

## 6. Fitting text and labels

- Wrap at a character budget on word boundaries, cap the line count (2-3 lines on a card), and end a cut summary at a word boundary with `...`.
- No widows: when the last line is one short word, pull the previous word down to join it if it fits.
- Chips with overflow: lay chips left to right (`width = 12 + chars * 6.2` at 9 px mono, 6 px apart). Before placing the next chip, reserve room for a `+N more` chip; if the chip plus the reserve does not fit, stop and draw `+N more` with the remaining count.
- Flip labels at edges: a label anchored `end` just left of its point flips to `start` just right of it when `x - 6 - chars * char_w` would cross the left margin (a chart peak on the first data point). Same logic on the right edge and for tooltips near the top.
- Clean input before drawing: escape every interpolated string (`html.escape`), drop emoji and XML-invalid control characters, and turn dash code points into a plain hyphen.

## 7. Theme variants

- A card that draws its own opaque background can ship as one file; it reads as a dark (or light) card on either GitHub theme.
- Transparent pieces (headers, dividers, footers, badges) ship as a dark and light pair through `<picture>` ([github-readme.md](github-readme.md) section 3). The light variant swaps ink to near-black and drops pale accents to their deep shade.
- Check both variants side by side before delivering; the light one is where contrast fails.

## 8. Element budgets

| Budget | Limit |
| --- | --- |
| animated elements in one scene | about 12 |
| animated elements in one file | about 40 |
| storyboard beats | 3-6 |
| depth layers | 3 |
| distinct hues | 1 accent + semantic green/amber/red when they mean something |
| file size | aim under 50 KB, hard stop 100 KB ([optimize.md](optimize.md)) |

Over budget reads as noise, costs CPU on every page that shows the README, and usually means the graphic is explaining two things.
