# Gotchas: symptom, cause, fix

Failures that cost real time on shipped README cards and in public projects. Find the symptom, apply the fix, re-run `validate_svg.py`.

## Renders on GitHub

| Symptom | Cause | Fix |
| --- | --- | --- |
| Works when opened locally, static or blank in the README | External font, image, `@import` or script; or inline `<svg>` pasted into Markdown | Reference the file as an image; inline assets as small data URIs; use system fonts ([github-readme.md](github-readme.md)); SV005 to SV009 catch these |
| Hover or click effect never fires in the README | An `<img>` receives no pointer events | Interaction only on the `web` target; README files animate on their own clock |
| Dark/light swap ignores GitHub's theme, wrong on iPhone and Safari | In-SVG `prefers-color-scheme` follows the OS, and WebKit does not apply it (bug 199134): https://github.com/orgs/community/discussions/62430 | Two files and a `<picture>` with `media` sources |
| Pale text or lines vanish on the light theme | Transparent file with light ink (blue 400, sky, green, amber are under 3:1 on white) | Draw an opaque card, ship a light variant, or use colors from [design.md](design.md) section 3 |
| Footer or divider looks dirty on light theme | Light-only neutrals on a transparent file | `rgba(127,127,127,0.28)` for hairlines; light variant for text |
| Images in a row stack vertically | `<img>` directly inside `<a>` gets `js-gh-image-fallback` (`display:block`) | `<a><picture><img></picture></a>`; verify with `gh api markdown` |
| A bare image links to its own raw file | GitHub auto-links bare `<img>` | Wrap in `<picture>` or your own `<a>` |
| `<details>` shows a triangle and focus ring; a table draws grid lines around cards | Default GitHub styles | Use `<p align="center">` rows |
| Animation does not run in Firefox on a README page | Open report on data-URI SVGs in Firefox: https://github.com/github/markup/issues/1864 | Keep animation in the top-level file; embed only static rasters |
| Old version keeps showing | Image proxy cache | Change the URL (`?v=2`); repo-relative files update with the commit |
| Card went blank after a scheduled run | A failed or partial API response was rendered | Treat partial errors as failure and keep the last good file |
| Entrance never seen | The clock starts at load; the card was below the fold | Make the final frame the real state; keep entrances short |
| Social preview or PNG export shows an empty card | Static renderers draw base values and every element starts at `opacity="0"` | Poster-safe entrance ([smil-and-css.md](smil-and-css.md) section 1) |

## SMIL

| Symptom | Cause | Fix |
| --- | --- | --- |
| Easing looks linear, keySplines ignored | `calcMode` misspelled or wrong case (`calcmod`, `calcmode`); XML attributes are case-sensitive. capsule-render ships this bug: https://github.com/kyechan99/capsule-render/blob/main/model/animationModel/waving.ts | Exact `calcMode="spline"`; `validate_svg.py` warns about keySplines without spline mode (SV018) |
| Animation does nothing at all | `values`, `keyTimes` and `keySplines` counts disagree (n, n, n - 1), or `keyTimes` does not start at 0 and end at 1 | Recount (SV017 and SV018 warn); generate the lists from one beat table |
| `keyPoints` on a packet ignored in some browsers, packet moves at constant speed | `animateMotion` defaults to `calcMode="paced"`, under which the spec ignores `keyTimes` (Chrome honors them anyway, so it looks fine there) | Add `calcMode="linear"` |
| Packet appears offset from its wire | The packet was drawn at its final position; `animateMotion` adds the path position to the element's own coordinates | Draw the packet around (0, 0) |
| A `skewX` or `translate` disappears when `animateTransform` starts | `animateTransform` replaces the `transform` attribute by default | `additive="sum"` |
| Spinner swings around the corner of the canvas | `type="rotate"` without a center | `from="0 cx cy" to="360 cx cy"` |
| Bars grow from the wrong edge | `type="scale"` scales around the user-space origin | Draw the bar at the origin of a translated `<g>` ([smil-and-css.md](smil-and-css.md) section 3) |
| Chained step never starts | Its `begin="x.end"` points at an id that was renamed or removed (often by SVGO `cleanupIds`) | Keep ids simple and stable; disable `cleanupIds` |
| Path morph works in Chrome, frozen in Safari | CSS `d` animation; Safari parses it with no effect: https://github.com/mdn/browser-compat-data/blob/main/css/properties/d.json | Morph with SMIL `<animate attributeName="d">` |
| Morph snaps instead of blending | The values have different command structures or point counts | Same commands, same order, same count of numbers in every value |
| `fill="freeze"` seems ignored on a loop | `repeatCount="indefinite"` never ends, so there is nothing to freeze | Expected; use freeze on one-shots |

## CSS in SVG

| Symptom | Cause | Fix |
| --- | --- | --- |
| Scale or rotate pivots around the SVG's top-left corner | `transform-origin` without `transform-box: fill-box` | Add `transform-box: fill-box` (Chrome 64, Firefox 55, Safari 11: https://api.webstatus.dev/v1/features/transform-box) |
| Element jumps to the top-left when its CSS animation starts | A CSS `transform` replaces the element's `transform` attribute entirely | Put the positioning transform on a parent `<g>`, animate the child |
| Item flashes visible, then fades in | `forwards` with a delay shows the resting state during the delay | `animation-fill-mode: both` |
| Ring stroke gets thick as it grows | CSS `scale` scales the stroke too | Animate `r` with SMIL, or accept it |
| `prefers-reduced-motion` block has no effect | The rule was inlined into a `style` attribute (outranks the media block), or the motion is SMIL | Keep rules in `<style>`; SMIL cannot be stopped by media queries ([timing.md](timing.md) section 7) |

## Line draws

| Symptom | Cause | Fix |
| --- | --- | --- |
| Draw stops short in Chrome | `pathLength` together with `vector-effect="non-scaling-stroke"` | No `vector-effect` on the animated path; keep a separate static hairline (SV019 warns) |
| Draw stops a hair short in Firefox | Rounding at 100% (https://gsap.com/docs/v3/Plugins/DrawSVGPlugin/) | Dash value about 2 units longer than the path |
| Draw shorter after zooming in Safari | `pathLength` rescaling bug: https://github.com/motiondivision/motion/issues/3301 | Use the computed length instead of `pathLength="1"` |
| Draw jumps or runs backwards in Safari | Negative `stroke-dashoffset`: https://www.svgator.com/help/technical-issues/path-animation-issues-in-safari | Animate from `+length` to `0` |
| `<rect>` outline draws oddly on iOS | iOS Safari rect stroke handling (same GSAP note) | Draw the outline as a `<path>` |
| A dot shows at the start before the draw | Round linecap on a zero-length visible dash | Start the offset slightly past the length, or fade the path in with the draw |

## Text and layout

| Symptom | Cause | Fix |
| --- | --- | --- |
| Double spaces vanish | SVG collapses runs of whitespace | Separate `<tspan>`/`<text>` with their own `x`, or `xml:space="preserve"` |
| Text overflows its pill or card on some machines | Width estimated for one font; the fallback differs per OS | Estimate with slack ([design.md](design.md) section 4); `textLength` as a last resort |
| Typing reveal clips the last character | Final clip width equals the estimate exactly | Make the last clip value generously wider than the line |
| Last line of a paragraph is one lonely word | Plain greedy wrapping | Pull the previous word down when it fits |
| Chart label runs off the left edge | Label always anchored `end` left of its point | Flip to `start` when it would cross the margin |
| Emoji show as boxes, or the file fails to parse | Emoji or XML-invalid characters from user data | Drop them and escape every interpolated string |
| `#abc14` renders black or not at all | 3-digit hex with an alpha suffix is invalid | Expand to 6 digits first, then append alpha |
| Text unreadable on phones | 840 px canvas scaled to about 0.41x | Key text at least 22-24 px drawn, or a narrower canvas |

## Ids, generation and tooling

| Symptom | Cause | Fix |
| --- | --- | --- |
| Icons show each other's gradients; clip paths go wrong when two files are inlined in one page | Id collisions; ids are global to the document | Prefix every id, `url(#)` and `href="#"` ([optimize.md](optimize.md) section 3); SV012 catches duplicates inside one file, not across files |
| Fade-in elements, defs or strokes missing after SVGO | Default preset (`removeHiddenElems`, `removeUselessDefs`, `removeUselessStrokeAndFill`...) | The animation-safe config in [optimize.md](optimize.md) |
| A patch to one element hit a different element | String surgery such as `.replace("<rect ", '<rect opacity="0" ', 1)` | Build attributes explicitly in the generator |
| Every scheduled run commits a diff | Timestamps, unstable ordering or CRLF output | Deterministic output, `newline="\n"`, write only when changed |
| Beats drift apart after a few loops | Elements on different durations | One clock; sub-loops divide it evenly ([timing.md](timing.md) section 4) |
| Loop jumps at the seam | Last value differs from the first, or the packet is visible while it resets | Equal ends; reset while hidden |
| Marquee shows a gap or a jump | Translated by something other than one row span (trailing gap forgotten), or the row is narrower than the window | Translate exactly `items * step`; repeat items until the span covers the window |
| Marquee edge fade shows colored bands | Fade painted as a card-colored overlay on a transparent file | Use a luminance `<mask>` |
| A third-party icon disappears after an upgrade | Icon fetched from a `@latest` CDN path that dropped the slug | Pin the version or vendor the icon |
