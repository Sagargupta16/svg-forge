# GitHub README delivery

What survives GitHub's pipeline, how to ship dark and light variants, the markup quirks that break layouts, and how to preview before merging. Everything here also holds for any page that shows the SVG through `<img>` (docs sites, npm and PyPI pages, most Markdown renderers).

## 1. How a README image reaches the reader

- GitHub sanitizes README HTML. Inline `<svg>`, `<style>` and `<foreignObject>` written into Markdown are stripped, so an SVG animates only when it is referenced as an image file. Sources: https://github.com/gjtorikian/html-pipeline/blob/main/lib/html_pipeline/sanitization_filter.rb , https://github.com/orgs/community/discussions/151372
- Reference it as `![alt](./assets/card.svg)` or `<img src="./assets/card.svg" alt="...">`. Repo-relative paths are the safe default: the file ships with the repo and updates with every commit.
- Images on other hosts go through GitHub's image proxy (camo). A fetched camo URL for readme-typing-svg answered with `Content-Type: image/svg+xml`, `Content-Security-Policy: default-src 'none'; img-src data:; style-src 'unsafe-inline'` and `Cache-Control: no-cache`. Inline `<style>` and `data:` URIs work; nothing external is fetched and no script runs. Source: https://github.com/DenverCoder1/readme-typing-svg
- An SVG shown through `<img>` never fetches external fonts or images, whatever the host sends. Source: https://stackoverflow.com/questions/72151299/svg-image-tag-doesnt-work-on-github-readme

## 2. What survives

| Feature | In a README image | Notes |
| --- | --- | --- |
| SMIL (`<animate>`, `<animateTransform>`, `<animateMotion>`, `<set>`) | works | readme-typing-svg animates `d` on a `<textPath>` path and chains lines with `begin="d0.end"`. https://github.com/DenverCoder1/readme-typing-svg/blob/main/src/templates/main.php |
| CSS `@keyframes` in an inline `<style>` | works | github-readme-stats fades and scales rows in with `animation-delay:(index+3)*150ms`. https://github.com/anuraghazra/github-readme-stats/blob/master/src/common/Card.js ; github-profile-trophy also uses CSS keyframes. https://github.com/ryo-ma/github-profile-trophy/blob/master/src/card.ts |
| `data:` URI images and fonts | works | Weight is the cost; see section 5. readme-typing-svg embeds its font as a base64 `@font-face`. |
| System font stacks | works | Glyph widths vary by OS; leave slack (see [design.md](design.md)). |
| `<script>`, event handlers, `javascript:` | blocked | No JS library runs inside a README image. |
| External `<image href="https://...">`, `@import`, `url(https://...)` fonts | blocked | Inline as a data URI or drop it. |
| `<foreignObject>` | do not use | Renders in Chromium and Firefox per write-ups, Safari unverified. https://dev.to/grahamthedev/take-your-github-readme-to-the-next-level-responsive-and-light-and-dark-modes--3kpc |
| Hover, focus, click (`:hover`, `begin="mouseover"`) | never fires | An `<img>` receives no pointer events inside the SVG. Interaction belongs to the `web` target only. |
| `prefers-color-scheme` inside the SVG | unreliable | Follows the OS, not GitHub's theme, and fails in WebKit. Use `<picture>` (section 3). |

`validate_svg.py --target standalone` checks the blocked rows for you: SV005 (`<script>`), SV006 (event handlers, `javascript:`), SV007 (`<foreignObject>`), SV008 (external references), SV009 (`@import`, remote fonts).

## 3. Dark and light: `<picture>`, not in-SVG media queries

Ship two files and let GitHub pick by its own theme setting:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/card-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/card-light.svg">
  <img alt="Build pipeline: commit, test, deploy, with a packet moving through each stage" src="./assets/card-light.svg">
</picture>
```

- GitHub documents this pattern: https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#specifying-the-theme-an-image-is-shown-to . The older `#gh-dark-mode-only` / `#gh-light-mode-only` URL fragments are deprecated there.
- GitHub renders `<picture>` as a `<themed-picture>` element, which follows the theme the reader chose on GitHub, not only the OS.
- Why not one SVG with `@media (prefers-color-scheme: dark)` inside: inside an image it evaluates against the OS, so a reader on a light OS with GitHub set to dark sees the wrong palette; and WebKit (Safari, the GitHub iOS app) does not apply it (WebKit bug 199134, confirmed by GitHub staff 2025-05-20). Sources: https://github.com/orgs/community/discussions/62430 , https://prlens.dev/guides/animated-svg-in-github-comments
- `forge.py --theme both --out assets/NAME.svg` writes `assets/NAME-dark.svg` and `assets/NAME-light.svg` and prints a snippet like the one above, with the paths exactly as passed to `--out` (so pass a repo-relative path) and the file's `<title>` as alt text: replace that alt with a real description ([accessibility.md](accessibility.md)).
- Single-file alternative: draw an opaque background (a card) so the file looks the same on both themes. Most cards do this; only transparent pieces (headers, dividers, footers) need a light variant.
- Transparent pieces must hold 3:1 against both `#ffffff` and `#0d1117`; see [design.md](design.md) section 3 for colors that do.

## 4. Markup quirks that break layouts

- **`<img>` directly inside `<a>` stacks vertically.** GitHub adds the class `js-gh-image-fallback` (with `display:block`) to any `<img>` that is a direct child of `<a>`, which defeats `<p align="center">` and `&nbsp;` spacing. Wrap the image in `<picture>`: `<a href="..."><picture><img src="..." alt="..."></picture></a>`. The wrapper looks redundant; it is load-bearing.
- **A bare `<img>` gets linked to itself.** GitHub wraps it in a link to the raw file. `<picture>` (or your own `<a>`) avoids that.
- **`<details>` always shows its triangle and focus box; tables draw grid lines.** For rows of cards use `<p align="center">` with images separated by spaces.
- **Side by side on desktop, stacked on phones.** Two 410 px wide cards with no `width` attribute sit side by side in an 840 px column and wrap onto separate lines on a phone, each scaled to the screen width. A `width="49%"` attribute keeps them side by side on phones too, at half the size. Check on a phone either way.
- Verify markup the way GitHub renders it:

```bash
gh api --method POST markdown -f mode=gfm -F text=@snippet.md > rendered.html
grep -c js-gh-image-fallback rendered.html   # want 0
```

## 5. Data URIs and size budgets

- Prefer drawing over embedding. Icons as paths (prefixed `<symbol>` plus `<use>`) cost far less than rasters.
- When a raster is unavoidable, embed it at 2x its drawn size: a certificate wall went from 728 KB to 310 KB that way, and a 658 KB image was dropped as too heavy. Caps that worked in practice: 64 KB per icon, 256 KB per logo.
- An embedded font dominates file size (the readme-typing-svg card is 9,886 bytes with its font). Use a system stack unless the font is the point; if it is, subset it to the glyphs you draw.
- Budgets: aim under 50 KB per file, hard stop at 100 KB unless the user accepts more. `validate_svg.py` errors above 100 KB and warns above 50 KB for `standalone` (SV013), warns on any data URI over 64 KB (SV020), and takes `--max-kb N` to change the budget. The open-source camo defaults to a 5,242,880-byte limit, a 10 s timeout and 4 redirects; GitHub's production limits are unpublished, so do not design near them. Source: https://github.com/atmos/camo
- Firefox caveat: an open report says data-URI SVGs do not animate in Firefox on README pages (github/markup#1864, closed as not planned). Keep animation in the top-level file, embed only static rasters as data URIs, and check Firefox when the file nests one SVG inside another. Source: https://github.com/github/markup/issues/1864

## 6. Hosting and caching

- Self-host: commit the SVG to the repo and regenerate it with a scheduled workflow. Hosted widget services fail under load (HTTP 402 from quota-limited hosts, shields.io token-pool errors); a committed file cannot go down.
- Make generation deterministic (same data, same bytes) and write the file only when it changed, so a quiet day produces no commit. On a failed data fetch, keep the last good file instead of rendering an empty card; treat partial API errors as failures.
- An external SVG that looks stale: the observed camo response carried `Cache-Control: no-cache`, but if an old copy persists, change the URL (`?v=2`) to force a fresh fetch. Repo-relative files update with the commit.

## 7. Clock and visibility

- The animation clock starts when the image loads, not when it scrolls into view. A one-shot entrance below the fold has usually finished before anyone sees it, so the final frame must be the real, complete state. Keep entrances under 5 s ([timing.md](timing.md)).
- Static renderers (social previews, PNG conversion with resvg, some Markdown viewers) show the file's base attribute values. If every element starts at `opacity="0"`, they show a blank card. Use the poster-safe entrance in [smil-and-css.md](smil-and-css.md) section 1.

## 8. Preview before merging

1. Open the file directly in Chrome, Firefox and Safari (or WebKit through Playwright). Watch at least two loop cycles for a seam.
2. For README work, push to a branch and open the README on GitHub for that branch. Switch GitHub's theme (Settings, Appearance) to check both `<picture>` sources.
3. Check the phone layout: open the branch README at 375 px wide (browser device mode) and on a real phone if possible.
4. Run `gh api markdown` (section 4) whenever cards sit inside links or share a row.
5. To inspect a SMIL frame exactly, pause and seek: `svg.pauseAnimations(); svg.setCurrentTime(2.4)` on an inline copy of the file. Playwright's `animations: "disabled"` freezes CSS and WAAPI only, not SMIL. Source: https://developer.mozilla.org/en-US/docs/Web/API/SVGSVGElement/setCurrentTime
