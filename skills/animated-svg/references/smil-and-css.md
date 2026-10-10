# SMIL and CSS cookbook

Proven techniques for standalone SVG files, each with a minimal snippet that renders inside `<img>`. Numbers come from cards that shipped on GitHub READMEs. Pick the mechanism first ([timing.md](timing.md) for durations, [design.md](design.md) for colors), then copy the closest recipe.

Both SMIL and CSS animate inside a README image. SMIL is Baseline widely available since 2022-07-15 (https://api.webstatus.dev/v1/features/smil-svg-animations).

## 0. SMIL or CSS?

| Need | Use | Why |
| --- | --- | --- |
| Geometry attributes (`d`, `r`, `width`, `x`, `points`) | SMIL `<animate>` | CSS cannot animate most of them; the CSS `d` property has no effect in Safari. |
| Motion along a path | SMIL `<animateMotion>` | Oldest and most portable; CSS `offset-path` is a web-target option. |
| Discrete steps (typing, ticking) | SMIL `calcMode="discrete"` or CSS `steps()` | Both work. |
| Sequences (`b` starts when `a` ends) | SMIL `begin="a.end"` | CSS has no event chaining; delays drift if one duration changes. |
| Transform and opacity on groups, simple fades | CSS `@keyframes` | Shorter, readable, `transform-box` gives sane pivots. |
| Anything that should honor `prefers-reduced-motion` | CSS | Media queries cannot stop SMIL. See [timing.md](timing.md) section 7. |

Mixing both in one file is fine. Never animate the same property of the same element with both.

Spelling matters: XML attributes are case-sensitive. `calcmod`, `calcmode` or `keysplines` are silently ignored (capsule-render ships `calcmod="spline"`, so its keySplines never apply: https://github.com/kyechan99/capsule-render/blob/main/model/animationModel/waving.ts). `validate_svg.py` warns about keySplines without `calcMode="spline"` (SV018) and about keyTimes/values counts that disagree (SV017).

## 1. Staggered one-shot entrance

SMIL, `fill="freeze"` keeps the end state. Item `i` begins at `0.1 + i * 0.08` s:

```xml
<g opacity="0">
  <animate attributeName="opacity" from="0" to="1" begin="0.26s" dur="0.45s" fill="freeze"/>
  <animateTransform attributeName="transform" type="translate" from="0 10" to="0 0"
    begin="0.26s" dur="0.45s" fill="freeze"
    calcMode="spline" keyTimes="0;1" keySplines="0.22 1 0.36 1"/>
  <rect x="16" y="16" width="190" height="80" rx="12" fill="#0f171c"/>
</g>
```

CSS, the same entrance. Write the resting state as the base style and animate only `from`; `both` applies the `from` frame during the delay and keeps the end state after:

```xml
<style>
  .in { animation: in 0.45s cubic-bezier(0.22, 1, 0.36, 1) both; }
  @keyframes in { from { opacity: 0; transform: translateY(10px); } }
</style>
<g class="in" style="animation-delay: 0.26s">...</g>
```

`forwards` alone also keeps the end state but shows the resting state during the delay, which flashes the item before it fades in.

**Poster-safe entrance.** Static renderers (link previews, resvg PNG export) ignore animation and draw base values, so a card whose items all start at `opacity="0"` exports blank. Keep the base visible and put the delay inside the animation, beginning at 0 s:

```xml
<g>
  <!-- delay 0.26 s + fade 0.45 s = 0.71 s; 0.26 / 0.71 = 0.366 -->
  <animate attributeName="opacity" values="0;0;1" keyTimes="0;0.366;1" dur="0.71s" fill="freeze"/>
  ...
</g>
```

The animation applies `0` from the first frame, so browsers never flash the item; static renderers show it at full opacity. The CSS version above is poster-safe already.

Instant reveal with no fade: `<set attributeName="opacity" to="1" begin="2.6s" fill="freeze"/>` on an element with `opacity="0"`.

## 2. Line draw

Known length (preferred for standalone). Set the dash to the path length plus about 2 units so Firefox does not stop a hair short:

```xml
<!-- segments: (20,80)-(120,40) = 107.7, (120,40)-(220,60) = 102.0; total 209.7 -> 212 -->
<path d="M20 80 L120 40 L220 60" fill="none" stroke="#2563eb" stroke-width="2"
  stroke-linecap="round" stroke-dasharray="212" stroke-dashoffset="212">
  <animate attributeName="stroke-dashoffset" from="212" to="0" begin="0.2s" dur="2.4s"
    fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.65 0 0.35 1"/>
</path>
```

Compute the length in the generator: sum of `math.dist` over polyline points; for curves, sample the curve or use `pathLength`.

`pathLength` shortcut: `pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"`, animate the offset to `0`. Caveats:
- `pathLength` rescales `stroke-dasharray` on every geometry element in current browsers; older Safari honored it only on `<path>` until version 14. Source: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/pathLength
- Safari zoom shortens a `pathLength`-normalized draw (Motion fixed it by switching to unitless dash values). Source: https://github.com/motiondivision/motion/issues/3301
- `pathLength` with `vector-effect="non-scaling-stroke"` stops short in Chrome (dash sized in user units, painted in screen units). Keep static hairlines and animated draws as separate elements; never put `vector-effect` on the animated one.
- Firefox may stop a stroke short of 100%; overshoot to about 102%. iOS Safari draws `<rect>` strokes badly; draw a `<path>` instead. Source: https://gsap.com/docs/v3/Plugins/DrawSVGPlugin/
- Safari handles negative `stroke-dashoffset` inconsistently. Always draw from `+length` to `0`, never from `0` to `-length`. Source: https://www.svgator.com/help/technical-issues/path-animation-issues-in-safari

CSS version: `.draw { stroke-dasharray: 212; stroke-dashoffset: 212; animation: draw 2.4s 0.2s cubic-bezier(0.65, 0, 0.35, 1) forwards; } @keyframes draw { to { stroke-dashoffset: 0; } }`. For a poster-safe CSS draw, leave the base offset at 0 and animate `from { stroke-dashoffset: 212; }` with `both`.

Travelling highlight (a comet along a wire, loops seamlessly): a short dash and a long gap whose sum is one period, offset animated over that period.

```xml
<path d="M0 110 C 140 80, 280 140, 420 110 S 700 80, 840 110" fill="none"
  stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-dasharray="120 900">
  <animate attributeName="stroke-dashoffset" values="1020;0" dur="4s" repeatCount="indefinite"/>
</path>
```

## 3. Bars grow

CSS: `transform-box: fill-box` makes `transform-origin` relative to the bar itself (without it the origin is the SVG's top-left corner). Supported since Chrome 64, Firefox 55, Safari 11 (https://api.webstatus.dev/v1/features/transform-box).

```xml
<style>
  .grow-x { transform-box: fill-box; transform-origin: left center;
            animation: gx 0.9s cubic-bezier(0.22, 1, 0.36, 1) both; }
  .grow-y { transform-box: fill-box; transform-origin: center bottom;
            animation: gy 0.9s cubic-bezier(0.22, 1, 0.36, 1) both; }
  @keyframes gx { from { transform: scaleX(0); } }
  @keyframes gy { from { transform: scaleY(0); } }
</style>
<rect class="grow-x" x="40" y="60" width="200" height="6" rx="3" fill="#2563eb" style="animation-delay: 0.6s"/>
```

SMIL: `animateTransform type="scale"` scales around the user-space origin, so draw the bar at the origin of a translated group and the baseline stays put in every engine:

```xml
<g transform="translate(40 120)">
  <rect x="0" y="-60" width="18" height="60" rx="3" fill="#2563eb">
    <animateTransform attributeName="transform" type="scale" values="1 0;1 0;1 1"
      keyTimes="0;0.4;1" dur="1.5s" fill="freeze"/>
  </rect>
</g>
```

(`values` with a leading hold is the poster-safe form of `begin="0.6s"`.) Stagger bars by 0.2 s each; a CSS bar with an attribute `transform` must move that transform to a parent `<g>` (see [gotchas.md](gotchas.md)).

## 4. Marquee (logo or icon strip)

Rules: duplicate the row (row + row), translate by exactly one row span, linear easing, duration = span / speed. The span must be at least the visible width; repeat the item list until it is, then duplicate.

```xml
<!-- 16 icons, step 58 (44 + 14 gap): span 928 >= 840 visible; 928 / 40 px/s = 23.2 s -->
<defs>
  <clipPath id="mq-win"><rect x="1" y="1" width="838" height="78" rx="14"/></clipPath>
  <linearGradient id="mq-fade" x1="0" x2="1">
    <stop offset="0" stop-color="#fff" stop-opacity="0"/>
    <stop offset="0.08" stop-color="#fff"/>
    <stop offset="0.92" stop-color="#fff"/>
    <stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
  <mask id="mq-mask"><rect width="840" height="80" fill="url(#mq-fade)"/></mask>
</defs>
<g clip-path="url(#mq-win)" mask="url(#mq-mask)">
  <g>
    <animateTransform attributeName="transform" type="translate" values="0 0;-928 0"
      dur="23.2s" repeatCount="indefinite"/>
    <use href="#i-0" x="0" y="18" width="44" height="44"/>
    <!-- ... items 1 to 15 at x = i * 58, then the same 16 again at x = 928 + i * 58 -->
  </g>
</g>
```

- Reverse direction (second row): `values="-928 0;0 0"`.
- Edge fade: the luminance mask works on any background. Painting a gradient overlay in the card color (what the shipped strip does) works only on an opaque card.
- Constant px/s keeps two rows of different lengths moving at the same visual speed; never give them the same duration.
- CSS equivalent: `.row { animation: mq 23.2s linear infinite; } @keyframes mq { to { transform: translateX(-928px); } }`.

## 5. Shine sweep

A skewed, faint gradient bar crossing a card, clipped to its rounded rect. `additive="sum"` keeps the `skewX` while the translate animates (without it the animation replaces the attribute). Sweep in the first 30% of the cycle, then rest:

```xml
<defs>
  <linearGradient id="shine" x1="0" x2="1">
    <stop offset="0" stop-color="#fff" stop-opacity="0"/>
    <stop offset="0.5" stop-color="#fff" stop-opacity="0.08"/>
    <stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
  <clipPath id="card-clip"><rect x="1" y="1" width="408" height="194" rx="16"/></clipPath>
</defs>
<g clip-path="url(#card-clip)">
  <rect x="-140" y="0" width="120" height="196" fill="url(#shine)" transform="skewX(-18)">
    <animateTransform attributeName="transform" type="translate" values="0 0;700 0;700 0"
      keyTimes="0;0.3;1" dur="6s" begin="0.7s" repeatCount="indefinite" additive="sum"/>
  </rect>
</g>
```

- Offset `begin` by about 0.7 s per card so a grid of cards does not flash in unison.
- White at 0.06 to 0.14 opacity reads on dark cards only; on a light card sweep the accent at 0.06 to 0.10.
- A header underline sweep (4.5 s) and a hero scan band (7 s) are the same recipe on a thin rect or a full-height band.

## 6. Pulse

Status dot ("live"): `<animate attributeName="opacity" values="1;0.35;1" dur="1.8s" repeatCount="indefinite"/>`.

Ripple ring, SMIL (stroke width stays constant because `r` grows, not a scale):

```xml
<circle cx="20" cy="20" r="4" fill="none" stroke="#22c55e" stroke-width="1.5">
  <animate attributeName="r" values="4;11" dur="2.2s" repeatCount="indefinite"
    calcMode="spline" keyTimes="0;1" keySplines="0.22 1 0.36 1"/>
  <animate attributeName="opacity" values="0.9;0" dur="2.2s" repeatCount="indefinite"/>
</circle>
```

Ripple ring, CSS (the stroke scales with the ring):

```css
.ring { transform-box: fill-box; transform-origin: center; animation: ring 2.2s ease-out infinite; }
@keyframes ring { 0% { opacity: 0.9; transform: scale(1); } 100% { opacity: 0; transform: scale(2.6); } }
```

Breathing node: `<animate attributeName="r" values="17;18.5;17" dur="3s" begin="0.4s" repeatCount="indefinite"/>`, with `begin` offset per node.

## 7. Packets on paths

`animateMotion` defaults to `calcMode="paced"`, and the SVG spec ignores `keyTimes` under `paced`. Chrome honored `keyPoints`/`keyTimes` with the default mode when checked (2026-10-10), so the bug hides there and appears in engines that follow the spec: always set `calcMode="linear"` with `keyPoints`. Window the trip inside one clock: wait, travel, fade, stay hidden until the loop restarts.

```xml
<path d="M46 92 H366" fill="none" stroke="rgba(127,127,127,0.35)" stroke-width="1.2"/>
<circle r="4" fill="#38bdf8" opacity="0">
  <animateMotion path="M46 92 H366" dur="6s" repeatCount="indefinite"
    calcMode="linear" keyPoints="0;0;1;1" keyTimes="0;0.08;0.62;1"/>
  <animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.08;0.62;0.64;1"
    dur="6s" repeatCount="indefinite"/>
</circle>
```

- Draw the packet around (0, 0): `animateMotion` adds the path position to the element's own coordinates.
- `rotate="auto"` turns arrows and chevrons along the path.
- To reuse a visible path, `<mpath href="#wire"/>` inside `animateMotion` avoids duplicating `d`; the inline `path` attribute is the most portable.
- Several packets on one wire: same `dur`, `begin` offsets of `dur / count` (or negative begins, section 12).
- Web target alternative: CSS `offset-path: path("M46 92 H366")` with `offset-distance` keyframes. Widely available since 2025-03-12 (`path()` from Safari 16, `url()` from Safari 17): https://api.webstatus.dev/v1/features/motion-path . Prefer `animateMotion` in standalone files.

## 8. Things taking turns on one keyTimes schedule (taglines, spotlight)

N lines (or tiles) share one clock `T = slot * N`. Line `i` owns the window `[i/N, (i+1)/N]` and fades for `f = fade_seconds / T` at each edge:

```
a = i / N        b = a + f        c = a + 1/N - f        d = a + 1/N
keyTimes = sorted unique {0, a, b, c, d, 1}
values   = 1 where b <= t <= c, else 0
```

Three lines, 3 s each, fade 0.36 s (T = 9 s, f = 0.04):

```xml
<text x="44" y="152" opacity="1">Line one
  <animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.04;0.293;0.333;1" dur="9s" repeatCount="indefinite"/></text>
<text x="44" y="152" opacity="0">Line two
  <animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;0.333;0.373;0.627;0.667;1" dur="9s" repeatCount="indefinite"/></text>
<text x="44" y="152" opacity="0">Line three
  <animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.667;0.707;0.96;1" dur="9s" repeatCount="indefinite"/></text>
```

The first line's base `opacity="1"` is what static renderers show; the animation overrides it from the first frame. A spotlight cycling over tiles is the same schedule applied to a highlight rect per tile (0.6 s slot per tile in the shipped grid).

Whitespace inside `<text>` collapses; keep each line's text on one line in the source (it is here: the newline sits before `<animate>`, which renders as one trailing space).

## 9. Typing via clipPath, discrete steps

Reveal a monospace line one character at a time by stepping a clip rect's width. With `calcMode="discrete"` and no `keyTimes`, each value holds for `dur / count`:

```xml
<clipPath id="type0">
  <rect x="24" y="30" width="0" height="20">
    <animate id="t0" attributeName="width" values="0;8.4;16.8;25.2;33.6;42;50.4;72"
      dur="0.6s" begin="0.3s" calcMode="discrete" fill="freeze"/>
  </rect>
</clipPath>
<text x="24" y="44" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
  font-size="14" fill="#e6edf3" clip-path="url(#type0)">make it</text>
```

- Step = 0.6 em (8.4 px at 14 px). Make the last value generously wider than the line (72 here, not 58.8) so a wider fallback font is never clipped.
- Speed: 10 to 20 characters per second reads as typing; 38 per second reads as a fast reveal.
- Next line: `begin="t0.end+0.4s"`. Output lines that appear whole: `<set attributeName="opacity" to="1" begin="t0.end" fill="freeze"/>`.
- Cursor: a rect whose `x` steps with the same discrete schedule, plus `<animate attributeName="opacity" values="1;0" calcMode="discrete" dur="1s" repeatCount="indefinite"/>` (CSS: `animation: blink 1s steps(1) infinite`).
- readme-typing-svg instead grows the `d` of a `<textPath>` path, which also works with proportional fonts.

## 10. Path morph (SMIL only for Safari)

The CSS `d` property animates in Chrome 52+ and Firefox 97+, while Safari parses it with no effect (https://github.com/mdn/browser-compat-data/blob/main/css/properties/d.json). Morph with SMIL. Every value needs the same commands, in the same order, with the same count of numbers; repeat the first value last for a seamless loop:

```xml
<path fill="#2563eb" fill-opacity="0.35" d="M0 40 C60 20 120 60 180 40 S300 20 360 40 V80 H0 Z">
  <animate attributeName="d" dur="8s" repeatCount="indefinite"
    calcMode="spline" keyTimes="0;0.5;1" keySplines="0.65 0 0.35 1;0.65 0 0.35 1"
    values="M0 40 C60 20 120 60 180 40 S300 20 360 40 V80 H0 Z;
            M0 40 C60 60 120 20 180 40 S300 60 360 40 V80 H0 Z;
            M0 40 C60 20 120 60 180 40 S300 20 360 40 V80 H0 Z"/>
</path>
```

Slow morphs (8 to 20 s) read as calm waves; capsule-render runs a 20 s wave.

## 11. Chaining with `begin="x.end"`

```xml
<animate id="a1" attributeName="opacity" from="0" to="1" begin="0.2s" dur="0.4s" fill="freeze"/>
<animate id="a2" attributeName="stroke-dashoffset" from="212" to="0" begin="a1.end" dur="1.2s" fill="freeze"/>
<set attributeName="opacity" to="1" begin="a2.end+0.2s" fill="freeze"/>
```

- Loop a chain by listing the start and the last link: `begin="0s;a3.end"` on the first animation.
- Ids used in `begin` stay simple: letters, digits and underscores (a `.` in an id needs escaping; avoid it).
- SVGO's `cleanupIds` rewrites ids and may keep only the first id of `begin="a.end;b.end"`; disable it ([optimize.md](optimize.md)).
- Chains suit one-shot sequences. For loops prefer one clock with `keyTimes` windows: a chain is only as robust as its first link, and a removed element silently stops everything after it.

## 12. Negative delays and phase offsets for ambient loops

Several identical loops started together pulse in unison. Start each at a different point of its cycle from the first frame:

- CSS: `animation-delay: -1.2s` starts the animation 1.2 s into its cycle at load (https://css-irl.info/quick-tip-negative-animation-delay/). Pair with a custom property per element: `style="--i: 3"` and `animation-delay: calc(var(--i) * -0.4s)`.
- SMIL: `begin="-1.2s"`; negative offsets are valid in SVG timing syntax (https://www.w3.org/TR/SVG11/animate.html#BeginAttribute), and Chrome started such an animation mid-cycle at the first frame when checked (2026-10-10). Check Safari before relying on it; the engine-proof alternative is rotating the `values` list per element (`0.3;1;0.3` vs `1;0.3;1`).
- `sibling-index()` would remove the per-element delays but is too new to rely on (Firefox 154, Safari 26.2): https://api.webstatus.dev/v1/features/sibling-count

## 13. Rotation, drift and other loops

- Spinner: `<animateTransform attributeName="transform" type="rotate" from="0 20 20" to="360 20 20" dur="1s" repeatCount="indefinite"/>`. Without the center (`20 20`) it rotates around the SVG origin. CSS: `transform-box: fill-box; transform-origin: center; animation: spin 1s linear infinite;`.
- Arc loader: a circle with `r="40"` (circumference 251.3) and `stroke-dasharray="60 191.3"` (dash plus gap equals the circumference, so exactly one arc shows) rotating, optionally with the dash length breathing on the same clock.
- Grid drift: animate a `<pattern>` by exactly one tile, `<animateTransform attributeName="patternTransform" type="translate" from="0 0" to="24 24" dur="30s" repeatCount="indefinite"/>`, for a seamless ambient background.
- Float: `@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }` at 4 s with per-item delays.
