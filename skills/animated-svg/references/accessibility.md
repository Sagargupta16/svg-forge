# Accessibility

How a standalone animated SVG gets a name, when it should be hidden, which contrast it needs, and what WCAG says about motion that a README image cannot pause.

## 1. Name the file itself

Every meaningful standalone file names itself, so it reads correctly when opened directly, inlined into a page, or embedded somewhere that passes the SVG's own semantics through:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="840" height="112" viewBox="0 0 840 112"
  role="img" aria-labelledby="card-title card-desc">
  <title id="card-title">Highlights</title>
  <desc id="card-desc">Four tiles: 128 commits this month, 12 releases, 3 open issues, 99.9 percent uptime.</desc>
  ...
</svg>
```

- `role="img"` + `<title>` + `<desc>` referenced by `aria-labelledby` is the most reliable pattern across screen readers. Source: https://www.smashingmagazine.com/2021/05/accessible-svg-patterns-comparison/
- `<title>` is the first child of the root. Keep it short (the name); put the content and numbers in `<desc>`.
- Prefix the `title`/`desc` ids when the file may be inlined next to others ([optimize.md](optimize.md) section 3).
- A one-attribute alternative that generators often use: `role="img" aria-label="..."` on the root.
- `validate_svg.py` requires one of these (SV010: `role="img"` with `aria-label` or `aria-labelledby`, or `aria-hidden="true"` for decoration) and checks that `aria-labelledby` points at a real `<title>`/`<desc>` (SV011). `forge.py` writes `role="img"`, `<title>`, `<desc>` and `aria-labelledby` with prefixed ids on every file.
- Keep text as real `<text>`, not outlined paths: it stays small, scales crisply and remains readable when inlined.

## 2. Alt text in README markup

Inside an `<img>` the SVG is a single picture; the `alt` attribute carries its meaning. Source: https://www.deque.com/blog/creating-accessible-svgs/

- `![Build pipeline: commit, test and deploy stages, a packet moving through each](./assets/pipeline.svg)` or `<img alt="..." src="...">`.
- Describe the content and its message, not the medium. "Animated SVG" or "banner" tells a screen-reader user nothing.
- Data cards: include the numbers (`GitHub stats: 1,204 contributions last year, 31 day streak, 85 stars`). Diagrams: one sentence of the flow. Taglines: list every rotating line, since a screen reader hears none of them otherwise.
- Reuse the SVG's own label for `alt` so the two never drift: generate both from the same string (unescape it for the Markdown).
- With `<picture>`, `alt` goes on the fallback `<img>` and covers both theme sources.

## 3. Decorative graphics

Dividers, waves, background marquees of logos and pure texture carry no information:

- In a README: empty alt, `<img alt="" src="./assets/divider.svg">` (Markdown `![](./assets/divider.svg)` produces the same).
- Inline in a page: `aria-hidden="true" focusable="false"` on the `<svg>`. Source: https://www.sarasoueidan.com/blog/accessible-icon-buttons/
- A logo strip is decorative only when the same tools are listed in text nearby; otherwise give it an alt that names them.

## 4. Contrast

- Text: 4.5:1 for body text, 3:1 for large text (at least 24 px, or 18.66 px bold). Source: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- Meaningful graphics (lines, nodes, chart marks, icons): 3:1 against their background (WCAG 1.4.11). Source: https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- Transparent files must pass against both `#ffffff` and `#0d1117`. No single color reaches 4.5:1 on both, so body text on a transparent file needs a `<picture>` pair or an opaque card; the table in [design.md](design.md) section 3 lists colors that pass 3:1 on both.
- Check the final frame and the dimmest frame of a loop: a label at 35% opacity mid-fade is decoration, but a label that rests at 35% must still meet the ratio.

## 5. Motion

- WCAG 2.2.2 Pause, Stop, Hide (Level A): motion that starts automatically, lasts more than 5 s and sits alongside other content needs a way to pause, stop or hide it. A README image cannot host a control. Source: https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html
  - One-shot entrances under 5 s comply.
  - Looping README files do not. That is the user's informed trade-off; say so when delivering.
  - On the `web` target, add a pause control to the page (`svg.pauseAnimations()` for SMIL, `animation-play-state: paused` for CSS).
- WCAG 2.3.1: nothing flashes more than three times per second. Blinks at 1 Hz or slower; never flash large areas. Source: https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html
- Never put information only in motion. Entrances finish before the reader scrolls to them, and static renderers draw one frame, so the resting frame must hold the whole message. Rotating taglines are the exception that alt text must cover.
- Reduced motion: motion stays visible by default. `forge.py --reduced-motion respect` is the user's opt-in; it freezes CSS animations under `prefers-reduced-motion: reduce` but cannot stop SMIL ([timing.md](timing.md) section 7).

## 6. Checklist before delivering

- [ ] Meaningful file: `role="img"`, `<title>`, `<desc>` (or `aria-label`), ids prefixed if it may be inlined.
- [ ] README markup has alt text with the content and numbers; decorative pieces have `alt=""`.
- [ ] Text meets 4.5:1 (3:1 large), graphics 3:1, on every theme the file can sit on.
- [ ] The resting frame carries the full message.
- [ ] Nothing flashes faster than 3 Hz; loops longer than 5 s are flagged to the user.
