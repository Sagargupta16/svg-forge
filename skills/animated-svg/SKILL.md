---
name: animated-svg
description: >-
  Designs, generates, validates and optimizes self-contained animated SVG
  files that render wherever an image can be shown, such as GitHub README
  cards, banners and headers, loaders, badges, dividers, charts and
  diagrams. CSS and SMIL only, five shared timing presets (micro, short,
  medium, long, ambient), a stdlib generator for ten common kinds and a
  validator with rule ids. Use when the user asks for an "animated SVG", a
  "README card", "README banner" or "README header", an "SVG loader", to
  "animate this SVG", a "line draw", an "SVG diagram for README", a "GitHub
  profile animation", or runs /animated-svg [create|animate|optimize].
  React and Motion scenes inside an app go to motion-scene; reviews of an
  existing file go to svg-audit.
argument-hint: "[create|animate|optimize] <what>"
---

# animated-svg

Build one self-contained `.svg` that animates on its own clock, survives GitHub's image pipeline, reads on dark and light themes, and stays small. Everything moves with SMIL or CSS inside the file; nothing loads from outside it.

Script paths below are relative to this skill's folder (the directory that holds this SKILL.md). Run them with Python 3.12+; they use the standard library only.

## Which skill

| Need | Skill |
| --- | --- |
| A standalone `.svg` for a README, docs site, package page or any `<img>`; or an SVG inlined in a plain HTML page | animated-svg (this one) |
| An animated React component using Motion (`motion/react`) inside an app | motion-scene |
| Review, debug or shrink an existing SVG or scene ("why doesn't it animate on GitHub") | svg-audit |

For a finished graphic end to end (storyboard, build, validate, iterate at every size), the plugin's `svg-designer` subagent follows this skill.

## Modes

- `create` (default): a new file from a description or data. Run the workflow below from step 1.
- `animate`: add motion to an existing static SVG. Read it, name the mechanism (step 3), then add techniques from [references/smil-and-css.md](references/smil-and-css.md) without changing its geometry. Prefix any ids you add. Then steps 5 to 7.
- `optimize`: make an existing animated file smaller without breaking it. Go straight to [references/optimize.md](references/optimize.md), then steps 5 and 6.

## Workflow

### 1. Pick the delivery target

| Target | Shown through | Allowed | Not allowed | Validate with |
| --- | --- | --- | --- | --- |
| `standalone` | `<img>` or a Markdown image: GitHub READMEs, docs, npm and PyPI pages | SMIL, CSS in an inline `<style>`, system fonts, small data URIs | script and event handlers, `<foreignObject>`, external `href`/`url()`/`@import`, hover and click, in-SVG theme switching | `--target standalone` |
| `web` | inline `<svg>` in a page you control | everything above, plus `:hover`/`:focus` and a page-level pause control | script inside the SVG; unprefixed ids (they collide with the page) | `--target web` |

Default to `standalone` when the file will be committed to a repo or shown on a site you do not control. GitHub strips inline `<svg>` from Markdown, so a README can only show the file as an image. Details, sources and the `<picture>` pattern for dark and light: [references/github-readme.md](references/github-readme.md).

### 2. Pick a timing preset

| Preset | Duration | Use when |
| --- | --- | --- |
| `micro` | 120-300 ms, one-shot | hover, press or toggle feedback; `web` target only (an `<img>` gets no pointer events) |
| `short` | 0.4-1.2 s one-shot, 60-120 ms stagger, total under ~1.5 s | data that should settle: stat tiles, charts drawing in, bars, list cards |
| `medium` (default) | 3-6 s seamless loop | one mechanism: packets on a wire, a pulse, a scan, a loader |
| `long` | 8-20 s storyboard loop, 3-6 beats on one clock | multi-step diagrams, rotating taglines, a terminal that types |
| `ambient` | 20-60 s, set by speed in px/s (default 40) | logo or tag strips, slow background drift |

The clock starts when the image loads, not when it scrolls into view, so a one-shot entrance below the fold has usually finished before anyone sees it: the final frame must be the complete, real state. Easing curves, stagger math, loop rules and the WCAG 2.2.2 note: [references/timing.md](references/timing.md).

### 3. Design the mechanism and storyboard before drawing

1. Write the subject as `input -> processing -> output` in its own nouns (read the code or the user's description, not a generic category).
2. Give every moving element a meaning: packet = request or artifact, line draw = progress, pulse = live, highlight = active step. Cut motion that means nothing.
3. Choose one clock `T`. Write the beat table: what moves, from where to where, during which fraction of `T`. Every element uses `T` (or `T / k`).
4. Check the budget: about 12 animated elements per scene, 40 per file, one accent plus neutrals, labels of 12 characters or fewer.

```
clock T = 6 s loop (medium)
| # | beat                      | t / T     | moves              |
| 1 | artifact appears at BUILD | 0.00-0.08 | packet fades in    |
| 2 | travels BUILD to DEPLOY   | 0.08-0.62 | packet on the wire |
| 3 | TEST lights as it passes  | 0.30-0.52 | node highlight     |
| 4 | rest, reset while hidden  | 0.90-1.00 | everything at rest |
```

Composition, grid, palette, contrast on both GitHub themes and type sizing: [references/design.md](references/design.md).

### 4. Generate with forge.py, or hand-author from a template

If a kind fits, generate it with `scripts/forge.py` and change the data, not the output:

| Kind | Draws | Default timing | `--data` shape |
| --- | --- | --- | --- |
| `tiles` | stat tiles grid; looping turns it into a spotlight | short | `[{"value": "42", "label": "repos", "tone": "ok"}]` (up to 16), or `{"items": [...], "cols": 4, "title": "..."}` |
| `hero` | title, rotating taglines, status pill, node constellation | long | `{"title": "Name", "kicker": "Hi", "taglines": ["One", "Two"], "status": "Live", "meta": "MIT", "nodes": ["api", "cli"]}` (up to 6 taglines; up to 8 nodes of 8 chars, shown when the canvas is at least 560 wide) |
| `marquee` | text chips scrolling at constant px/s | ambient | `["python", "rust"]` or `{"rows": [["a", "b"], ["c", "d"]]}` (up to 3 rows, alternating direction) |
| `chart` | line chart that draws in, area, peak marker | short | `{"values": [120, 150, 190], "labels": ["W1", "W2", "W3"], "unit": "", "peak": "PEAK"}` (at least 2 values) |
| `bars` | labelled progress bars that grow | short | `{"items": [{"label": "Python", "value": 46}], "unit": "%"}`; optional `max` and `tone` per item (up to 12) |
| `flow` | nodes and edges with packets: pipeline or architecture | medium | `{"nodes": ["commit", {"id": "deploy", "tone": "ok"}], "edges": [["commit", "deploy"]]}` (2-12 nodes in flow order; an edge back to an earlier node is a return arc) |
| `loader` | spinner, dots or bar (`--variant`); loops unless `--once` | medium | none; one turn is 0.6 / 0.9 / 1.2 / 2.0 / 4.0 s for micro / short / medium / long / ambient |
| `typing` | terminal that types commands, then shows output | long | `{"title": "bash", "prompt": "$", "lines": [{"cmd": "make build", "out": ["done"], "tone": "ok"}]}` (up to 8 lines) |
| `divider` | hairline with a center dot and a pulse | medium | none; transparent, so use `--theme both` |
| `badge` | label and value pill with a status dot and shine | medium | `{"label": "build", "value": "passing", "tone": "ok", "dot": true}` |

`tone` is `accent` (default), `ok`, `warn`, `muted` or a hex color.

Common options:
- `--kind KIND` (required), `--out FILE` (omit to print one theme to stdout).
- `--width`, `--height` in px (8 to 4000; most kinds size to content).
- `--theme dark|light|both` (default `dark`). `both` needs `--out` and writes `NAME-dark.svg` and `NAME-light.svg`, then prints a `<picture>` snippet using the paths exactly as given, so pass a repo-relative path such as `--out assets/hero.svg`.
- `--accent "#rrggbb"` or `#rgb` (default `#60a5fa`). Ink is clamped per theme (at least 60% lightness on dark, at most 42% on light) so text and strokes stay legible.
- `--timing micro|short|medium|long|ambient` (kind default otherwise); `--loop` or `--once` overrides looping; `--speed` sets px/s for marquee and ambient (default 40).
- `--title` (visible heading where the kind has one, and the `<title>`), `--desc` (overrides the generated `<desc>`).
- `--data` inline JSON or a path to a JSON file. Prefer a file on Windows shells, where inline JSON quoting differs.
- `--variant spinner|dots|bar` (loader), `--reduced-motion ignore|respect` (default `ignore`; kinds move mostly through SMIL, so `respect` freezes only their CSS parts, see [references/timing.md](references/timing.md) section 7), `--font-stack sans|mono|serif|system` or a font-family list, `--id-prefix` (default: a hash of the input, so ids and classes never collide when files are inlined together).

```bash
python scripts/forge.py --kind flow --timing long --data pipeline.json --out assets/flow.svg
python scripts/forge.py --kind tiles --data stats.json --out assets/tiles.svg
python scripts/forge.py --kind hero --theme both --accent "#a78bfa" --title "Project" --out assets/hero.svg
python scripts/forge.py --kind loader --variant dots --once --out assets/dots.svg
```

Output is deterministic (same input, same bytes, LF) and a file is rewritten only when its bytes change, so scheduled runs commit nothing on a quiet day. Bad options or data exit with status 2 and a message.

Starter templates (all pass the validator): `assets/templates/tiles.svg`, `assets/templates/hero.svg` and `assets/templates/hero-light.svg`, `assets/templates/marquee.svg` and `assets/templates/marquee-ambient.svg`, `assets/templates/chart.svg`, `assets/templates/bars.svg`, `assets/templates/flow.svg` (medium loop), `assets/templates/flow-long.svg` (storyboard) and `assets/templates/flow-short.svg` (one-shot), `assets/templates/loader.svg`, `assets/templates/typing.svg`, `assets/templates/divider.svg`, `assets/templates/badge.svg`.

If no kind fits, hand-author: start from the closest starter template (forge output with sample data, already validated), keep its frame, prefixed ids and `role`/`<title>`/`<desc>` block, and add motion one recipe at a time from [references/smil-and-css.md](references/smil-and-css.md). Choose SMIL for geometry, paths, morphs, discrete steps and chains; CSS for transform and opacity on groups and anything that should honor reduced motion.

### 5. Validate

```bash
python scripts/validate_svg.py assets/hero-dark.svg assets/hero-light.svg --target standalone
```

- `FILE_OR_DIR...` one or more files, or folders to scan for `*.svg`; `--target standalone|web` (default `standalone`; `web` downgrades external references, `<foreignObject>` and a missing xmlns to warnings); `--max-kb N` (error above N, warning above half; defaults 100 KB standalone, 200 KB web); `--json` for machine-readable findings.
- Each finding has a rule id, severity and line. Exit status is 1 when any file has an error. Fix every error: SV001-SV004 structure, SV005-SV009 blocked content (script, handlers, `<foreignObject>`, external references, `@import` and remote fonts), SV010-SV011 accessible name, SV012 duplicate ids, SV013 size, SV014 en or em dashes.
- Then read the warnings: SV017 and SV018 (keyTimes, values and keySplines counts, keySplines without `calcMode="spline"`) usually mean an animation silently does nothing; SV015 more than 40 animated elements; SV016 a repeat under 100 ms; SV019 `pathLength` with `non-scaling-stroke`; SV020 a data URI over 64 KB.
- Generated files: fix the data or the generator, never the output.
- Symptom lookup when something renders wrong: [references/gotchas.md](references/gotchas.md).

### 6. Look at it

A passing validator is not a working animation.

1. Open the file directly in Chrome and Firefox (and Safari or WebKit when you can). Watch two full cycles; the seam is where loops break.
2. Seek exact frames: with the `.svg` open as its own page, run `document.documentElement.pauseAnimations(); document.documentElement.setCurrentTime(2.4)` in the console for SMIL, and `document.getAnimations().forEach(a => { a.pause(); a.currentTime = 2400; })` for CSS. Check each beat boundary from the storyboard. With browser automation tools, screenshot those frames.
3. README files: push to a branch and view the README on GitHub for that branch, in both GitHub themes, and at 375 px wide. An 840 px card renders at about 0.41x on a phone; anything that must be read needs about 22-24 px drawn size.
4. Rows of cards or images inside links: render the snippet with `gh api --method POST markdown -f mode=gfm -F text=@snippet.md` and confirm no `js-gh-image-fallback` class appears.
5. Accessibility: the file names itself (`role="img"`, `<title>`, `<desc>`); the README markup carries real alt text with the content and numbers (replace forge's title-only alt in the printed snippet); decorative pieces use `alt=""`. See [references/accessibility.md](references/accessibility.md).

### 7. Optimize safely

- Skip SVGO for forge output; it is already compact.
- For exported artwork, use the animation-safe SVGO v4 config (default `preset-default` deletes fade-in start states, rewrites ids that `begin` points at, and turns animated shapes into paths), then re-run step 5 and compare animation counts before and after.
- Budgets: aim under 50 KB, hard stop 100 KB unless the user accepts more; rasters at 2x drawn size; no embedded fonts unless the font is the point.

All of it, with the config and the reasons: [references/optimize.md](references/optimize.md).

## Deliver

Hand back:
- the file paths and sizes (both theme files when `both`);
- the README markup: the `<picture>` snippet or `<img>`, with descriptive alt text;
- the timing preset and the beat table used;
- the validator result, and which browsers, frames, themes and widths were checked;
- anything not verified (for example Safari not available), and a note when a README loop runs longer than 5 s (WCAG 2.2.2 cannot be met inside an image).

## Never do

- Never put `<script>`, event handlers, `<foreignObject>`, external `href`/`url()`/`@import` or web-font URLs in a standalone file.
- Never paste inline `<svg>` into Markdown or rely on hover and click inside an `<img>`.
- Never switch themes with `prefers-color-scheme` inside the file for a README; ship a `<picture>` pair.
- Never put pale accents or light text on a transparent file without a light variant.
- Never put information only in motion: the resting frame holds the whole message.
- Never run beats on different clocks or ship a loop that jumps at its seam.
- Never animate `d` with CSS (Safari ignores it) or draw lines with a negative `stroke-dashoffset`.
- Never run SVGO's default preset on an animated file or hand-edit a generated one.
- Never interpolate unescaped user text, emoji or dash characters into SVG text.
- Never add a reduced-motion gate by default (motion stays visible; `--reduced-motion respect` is the user's opt-in), and never add one to an app that has its own motion control.
- Never ship without running the validator and looking at the result.

## References

- [references/github-readme.md](references/github-readme.md): what survives GitHub's sanitizer and image proxy, `<picture>` for dark and light, the `<img>` inside `<a>` quirk, data URIs, size budgets, caching, the Firefox caveat, previewing.
- [references/smil-and-css.md](references/smil-and-css.md): copy-paste recipes for entrances, line draws, bars, marquees, shine, pulse, packets on paths, rotating taglines, typing, morphs, chaining and phase offsets; SMIL versus CSS.
- [references/timing.md](references/timing.md): the five presets, easing curves, stagger math, one-clock storyboards, seamless loops, length budgets, WCAG 2.2.2 and the reduced-motion trade-off.
- [references/design.md](references/design.md): mechanism over decoration, layout grids, palette and contrast on both GitHub themes, typography and width estimates, chips and label fitting, element budgets.
- [references/optimize.md](references/optimize.md): animation-safe SVGO v4 config, id prefixing, size budgets, determinism.
- [references/gotchas.md](references/gotchas.md): symptom, cause and fix for the failures that cost the most time.
- [references/accessibility.md](references/accessibility.md): naming the file, alt text, decorative graphics, contrast, motion and WCAG.
