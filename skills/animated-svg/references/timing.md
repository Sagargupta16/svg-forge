# Timing

Five presets, easing curves, stagger math, one-clock storyboards, seamless loops and length budgets. The preset names are shared across this plugin (`forge.py --timing`, the svg-designer agent, motion-scene).

## 1. The five presets

| Preset | Duration | Shape | Use for | Avoid for |
| --- | --- | --- | --- | --- |
| `micro` | 120-300 ms | one-shot | hover, press and toggle feedback; a pop at the end of a sequence | anything in a README: an `<img>` receives no pointer events, so feedback never fires |
| `short` | 0.4-1.2 s per item, total under about 1.5 s | one-shot entrance, `fill="freeze"` / `forwards`, stagger 60-120 ms per item | stat tiles, list cards, charts drawing in, badges, headers | content below the fold that must be watched (the clock starts at load) |
| `medium` (default) | 3-6 s | seamless loop | one mechanism: packets on a wire, a pulse, a scan, a breathing node | multi-step stories (they feel rushed) |
| `long` | 8-20 s | storyboard loop of 3-6 beats on one shared clock | multi-step diagrams, rotating taglines (about 3 s per line) | a single repeating motion (it feels sluggish) |
| `ambient` | 20-60 s, defined by speed in px/s (default 40) | slow drift or marquee | logo strips, background grid drift, slow waves | anything the reader must notice |

For comparison, Material 3's UI duration tokens are short 50-200 ms, medium 250-400 ms, long 450-600 ms and extra long 700-1000 ms (https://m3.material.io/styles/motion/easing-and-duration/tokens-specs). Those are UI transitions, which is why `micro` and `short` live in that band and everything longer here is a loop.

Pick by asking, in order:
1. Will the reader interact with it? Only possible on the `web` target: `micro`.
2. Is it data that should settle into a readable state? `short`; the final frame is the content.
3. Does one motion explain the mechanism? `medium`.
4. Does it take several ordered steps? `long`, 3-6 beats.
5. Is it texture or a strip? `ambient`.

`forge.py --timing PRESET` overrides each kind's default (tiles, chart and bars default to `short`; flow, loader, divider and badge to `medium`; hero and typing to `long`; marquee to `ambient`). `--loop` / `--once` override loop versus one-shot (a looping `tiles` becomes a spotlight cycling the tiles; a one-shot loader plays once), and `--speed` sets px/s for marquee and ambient timing (default 40). A loader turn takes 0.6 / 0.9 / 1.2 / 2.0 / 4.0 s for micro / short / medium / long / ambient.

## 2. Easing

SMIL easing needs three attributes together: `calcMode="spline"`, `keyTimes` and `keySplines`. With `n` values there are `n` keyTimes (first 0, last 1) and `n - 1` keySplines, one per segment, each `x1 y1 x2 y2` in 0..1. A count mismatch makes browsers drop the whole animation; a misspelled `calcMode` silently falls back to linear.

| Curve | `keySplines` | CSS | Use |
| --- | --- | --- | --- |
| ease-out (enter) | `0.22 1 0.36 1` | `cubic-bezier(0.22, 1, 0.36, 1)` | entrances, bars, draws that settle |
| ease-in-out | `0.65 0 0.35 1` | `cubic-bezier(0.65, 0, 0.35, 1)` | back-and-forth loops, morphs, line draws |
| ease-in (exit) | `0.55 0 1 0.45` | `cubic-bezier(0.55, 0, 1, 0.45)` | leaving before a reset |
| standard | `0.25 0.1 0.25 1` | `ease` | general purpose |
| linear | `calcMode="linear"` (the default for `<animate>`) | `linear` | marquees, rotation, packets, scans: constant speed reads as flow |
| steps | `calcMode="discrete"` | `steps(n)` / `steps(1)` | typing, ticking, cursor blink |

Hold segments (two equal adjacent values) can take `0 0 1 1`. CSS applies `animation-timing-function` per keyframe segment as well, so a multi-stop keyframe eases each leg.

```xml
<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.2;0.8;1" dur="4s"
  repeatCount="indefinite" calcMode="spline"
  keySplines="0.22 1 0.36 1;0 0 1 1;0.55 0 1 0.45"/>
```

## 3. Stagger math

```
begin_i = base + i * step
total   = base + (n - 1) * step + dur
```

Eight tiles, `base` 0.1 s, `step` 0.08 s, `dur` 0.45 s: 0.1 + 0.56 + 0.45 = 1.11 s, inside the `short` budget.

- Cap the spread: if `(n - 1) * step` exceeds about 0.6 s, shrink `step` to `0.6 / (n - 1)`, or stagger by row (`base + row * 0.12 + col * 0.04`) or diagonally (`base + (row + col) * step`).
- CSS options: an inline `style="animation-delay: 0.34s"` per item, a custom property (`style="--i: 3"` with `animation-delay: calc(var(--i) * 80ms + 100ms)`), or generated classes (`.d0` ... `.dN`); a shipped contribution calendar used one class per week at `0.4 + i * 0.03` s. Per-item delays with `--i` and `calc()` are the portable form (https://css-irl.info/quick-tip-negative-animation-delay/).
- Stagger in reading order (left to right, top to bottom) unless the mechanism has its own order.

## 4. Storyboards on one clock

Write the beat table before drawing anything. Every animated element in the scene then uses the same `dur` (the clock `T`) with `keyTimes` windows, so beats never drift apart. A secondary loop may run at `T / k` for a whole number `k` (a 2 s pulse inside a 6 s story stays in phase); any other duration drifts.

Example, a 6 s training pipeline (shipped as a README card):

| # | Beat | Window (t / T) | Seconds | What moves |
| --- | --- | --- | --- | --- |
| 1 | artifact appears at DATA | 0.00-0.08 | 0.00-0.48 | packet fades in |
| 2 | artifact travels DATA to SERVE | 0.08-0.62 | 0.48-3.72 | packet on the wire |
| 3 | GATE flashes green as it passes | 0.30-0.52 | 1.80-3.12 | gate highlight |
| 4 | drift arc lights, amber packet returns to TRAIN | 0.66-0.90 | 3.96-5.40 | dashed arc, second packet |
| 5 | rest, reset while hidden | 0.90-1.00 | 5.40-6.00 | everything at rest |

An element visible during `[s, e]` with an edge fade `f` gets:

```
values   = 0;0;1;1;0;0
keyTimes = 0;s;s+f;e-f;e;1      (drop the duplicate when s = 0 or e = 1)
```

Beat 3 with `f = 0.04`: `values="0;0;1;1;0;0" keyTimes="0;0.3;0.34;0.48;0.52;1" dur="6s"`.

Keep the table in the generator (or as a short comment in a hand-authored file) so later edits move a window instead of guessing at numbers.

## 5. Seamless loop rules

- The last value equals the first (`values="0.3;1;0.3"`, a morph's first path repeated last, rotate 0 to 360).
- Reset while invisible: a packet fades out, jumps home hidden, and fades back in.
- Translate loops move exactly one period: one marquee row span, one pattern tile, one dash-plus-gap length.
- Enter and leave the seam with matching easing (linear, or ease-in-out on both ends).
- Use durations that are exact in decimal (1.6 s, 23.2 s), rounded to 0.1 s when computed, and one clock per scene.
- Chain-based loops restart with `begin="0s;last.end"` on the first link.
- Watch two full cycles before shipping; the seam is where loops fail.

Two loop shapes, decided by what the first frame shows. A **build-up** loop starts empty, parts arrive, everything holds until about 0.90 to 0.92 and is gone by 0.94 to 0.95, then resets while hidden (`forge.py` does this with its veil); it needs a static ghost layer (dim nodes, wires, empty slots) that never animates, so the poster still reads as the diagram. A loop that **opens on the finished state** shows the complete mechanism at t=0, clears it at about 0.03 to 0.08, rebuilds it and holds to the end:

```xml
<animate attributeName="opacity" values="1;1;0;0;1;1" keyTimes="0;0.04;0.08;0.46;0.5;1"
  dur="6s" repeatCount="indefinite"/>
```

Prefer it when the end state alone explains the subject (a published chapter, an optimised bill): the poster is the finished thing, not an empty stage. Prefer the build-up when the story is a pipeline whose end state needs its steps. Either way every reset happens at opacity 0, and a still capture takes three frames across the cycle and keeps the one that shows the finished state.

## 6. Length budgets

| Thing | Budget |
| --- | --- |
| entrance, whole sequence | under 1.5 s for `short`; never over 5 s |
| one-mechanism loop | 3-6 s |
| storyboard | 8-20 s, 3-6 beats, each beat at least about 1 s |
| ambient speed | 20-60 px/s, default 40 |
| rotating tagline | about 3 s per line, fade 0.3-0.5 s |
| typing | 10-20 characters per second |
| status pulse | 1.8-2.2 s |
| spinner turn | 0.8-1.5 s |
| animated elements | about 12 per scene, 40 per file ([design.md](design.md) section 8) |

## 7. WCAG 2.2.2 and the reduced-motion option

WCAG 2.2.2 Pause, Stop, Hide (Level A): moving, blinking or scrolling content that starts automatically, lasts more than 5 seconds and runs alongside other content needs a way to pause, stop or hide it (https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html). A README image cannot host a control. So:
- One-shot entrances under 5 s comply.
- Loops in a README image do not; that is a trade-off the user makes knowingly. Say so when delivering a looping README file.
- On the `web` target, give the page a pause control: `svg.pauseAnimations()` for SMIL plus `animation-play-state: paused` for CSS.

Motion stays visible by default in this plugin. `forge.py --reduced-motion ignore|respect` defaults to `ignore`. `respect` (opt-in) adds a `@media (prefers-reduced-motion: reduce)` block that freezes CSS animations at their final frame. The trade-off:
- Media queries cannot stop SMIL. `forge.py` animates almost everything with SMIL, so under `respect` only its CSS animations freeze (the typing cursor blink, and the peak ring of a looping chart); the rest keeps moving. When reduced motion must be honored fully, hand-author with CSS-only techniques for everything that moves, or offer a static file.
- Inside an image, media queries evaluate against the OS setting (as `prefers-color-scheme` does), and WebKit's behavior there is unverified.
- Author the resting state as the base style and animate only `from` the start state; then freezing, `animation: none` and static renderers all land on the final frame.
- A `<picture>` with a `<source media="(prefers-reduced-motion: reduce)" srcset="card-static.svg">` works in plain HTML pages; whether GitHub's `<picture>` handling passes that media query through is unverified.

Separately from 2.2.2, nothing may flash more than three times per second (WCAG 2.3.1, https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html): keep blinks at 1 Hz or slower and never flash large areas.
