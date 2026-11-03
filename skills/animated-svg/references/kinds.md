# Kinds and options

Every `forge.py` kind with what it draws, its default timing and its `--data` shape, then every option. [SKILL.md](../SKILL.md) step 4 decides whether a kind fits; this is the lookup.

## Kinds

| Kind | Draws | Default timing | `--data` shape |
| --- | --- | --- | --- |
| `tiles` | stat tiles grid; looping turns it into a spotlight | short | `[{"value": "42", "label": "repos", "tone": "ok"}]` (up to 16), or `{"items": [...], "cols": 4, "title": "..."}` |
| `hero` | title, rotating taglines, status pill, node constellation | long | `{"title": "Name", "kicker": "Hi", "taglines": ["One", "Two"], "status": "Live", "meta": "MIT", "nodes": ["api", "cli"]}` (up to 6 taglines; up to 8 nodes of 8 chars, shown when the canvas is at least 560 wide) |
| `marquee` | text chips scrolling at constant px/s | ambient | `["python", "rust"]` or `{"rows": [["a", "b"], ["c", "d"]]}` (up to 3 rows, alternating direction) |
| `chart` | line chart that draws in, area, peak marker | short | `{"values": [120, 150, 190], "labels": ["W1", "W2", "W3"], "unit": "", "peak": "PEAK"}` (at least 2 values) |
| `bars` | labelled progress bars that grow | short | `{"items": [{"label": "Python", "value": 46}], "unit": "%"}`; optional `max` and `tone` per item (up to 12) |
| `flow` | nodes and edges with packets: pipeline or architecture | medium | `{"nodes": ["commit", {"id": "deploy", "tone": "ok"}], "edges": [["commit", "deploy"]]}` (2-12 nodes in flow order; an edge back to an earlier node is a return arc), or a text spec, inline or a `.txt` file: `push -> build -> unit, e2e -> deploy` (comma = parallel, `-[label]->` labels an edge, newline or `;` between statements, `#` comments) |
| `loader` | spinner, dots or bar (`--variant`); loops unless `--once` | medium | none; one turn is 0.6 / 0.9 / 1.2 / 2.0 / 4.0 s for micro / short / medium / long / ambient |
| `typing` | terminal that types commands, then shows output | long | `{"title": "bash", "prompt": "$", "lines": [{"cmd": "make build", "out": ["done"], "tone": "ok"}]}` (up to 8 lines) |
| `divider` | hairline with a center dot and a pulse | medium | none; transparent, so use `--theme both` |
| `badge` | label and value pill with a status dot and shine | medium | `{"label": "build", "value": "passing", "tone": "ok", "dot": true}` |
| `timeline` | career or history rail that draws in; the current item pulses (`--variant vertical` for a column) | long | `{"title": "Career", "items": [{"start": "2019", "end": "2022", "title": "Senior engineer", "subtitle": "Search"}, {"start": "2024", "title": "Lead", "current": true}]}` (up to 12 items; only an item marked `"current": true` pulses, and without an `end` it reads "start - now") |
| `logos` | logo wall; `--timing ambient` turns it into a marquee | short | `{"title": "Trusted by", "items": [{"label": "Acme", "svg": "logos/acme.svg", "color": "#38bdf8"}, {"label": "Ember", "image": "logos/ember.png"}, {"label": "Text only"}]}` (SVGs inline with prefixed ids, PNG/WebP up to 64 KB as data URIs, a bare label is a text pill; paths from the working directory) |
| `calendar` | 53-week contribution heatmap with quartile levels (`--variant accent` uses the accent ramp) | short | `{"days": [{"date": "2025-10-07", "count": 10}]}` or `{"start": "2025-10-05", "counts": [4, 0, 5]}` |
| `ring` | progress rings that draw in to static values | short | `{"title": "Goals", "items": [{"label": "Coverage", "value": 91}, {"label": "Issues", "value": 42, "max": 60, "tone": "ok"}]}` |

`tone` is `accent` (default), `ok`, `warn`, `muted` or a hex color.

## Options

- `--kind KIND` (required), `--out FILE` (omit to print one theme to stdout).
- `--size`: `WxH`, a width, or a preset (`readme`, `card`, `og`, `linkedin-banner`, `square`, `story`, `icon-128` and more). timeline, logos, calendar and ring lay out natively; the other ten scale their layout in, centered and never distorted, but their labels do not grow, so keep icon sizes to native kinds or marks. Use it or `--width`/`--height` (8 to 4096), not both.
- `--theme`: `dark` (default), `light`, `both` (the GitHub pair), a preset (`nord`, `dracula`, `catppuccin-mocha`, `tokyo-night`, ...), a family, `auto:<hex>` for a brand color, or a palette `.json`. `--mode dark|light|both` picks a family's variant; `both` needs `--out`, writes `NAME-dark.svg` and `NAME-light.svg` and prints a `<picture>` snippet with the paths as given, so pass a repo-relative `--out`.
- `--accent "#rrggbb"` (default: the theme's own). Text reaches 4.5:1 and marks 3:1 in every theme; a color that falls short, your accent included, moves to the nearest passing lightness and is noted on stderr.
- Every preset, the native and scaled kinds, palette files and the contrast rules: [references/themes-and-sizes.md](themes-and-sizes.md).
- `--timing micro|short|medium|long|ambient` (kind default otherwise); `--loop` or `--once` overrides looping; `--speed` sets px/s for marquee and ambient (default 40).
- `--title` (visible heading where the kind has one, and the `<title>`), `--desc` (overrides the generated `<desc>`).
- `--data` inline JSON or a path to a JSON file. Prefer a file on Windows shells, where inline JSON quoting differs.
- `--variant spinner|dots|bar` (loader), `--reduced-motion ignore|respect` (default `ignore`; kinds move mostly through SMIL, so `respect` freezes only their CSS parts, see [references/timing.md](timing.md) section 7), `--font-stack sans|mono|serif|system` or a font-family list, `--id-prefix` (default: a hash of the input, so ids and classes never collide when files are inlined together).

```bash
python scripts/forge.py --kind flow --timing long --data pipeline.json --out assets/flow.svg
python scripts/forge.py --kind tiles --data stats.json --out assets/tiles.svg
python scripts/forge.py --kind hero --theme both --accent "#a78bfa" --title "Project" --out assets/hero.svg
python scripts/forge.py --kind loader --variant dots --once --out assets/dots.svg
python scripts/forge.py --kind ring --theme nord --size og --data goals.json --out assets/goals.svg
python scripts/forge.py --kind timeline --theme catppuccin --mode both --size readme --data career.json --out assets/career.svg
```

Output is deterministic (same input, same bytes, LF) and a file is rewritten only when its bytes change, so scheduled runs commit nothing on a quiet day. Bad options or data exit with status 2 and a message.

## Starter templates

Every file passes the validator: `assets/templates/tiles.svg`, `assets/templates/hero.svg` and `assets/templates/hero-light.svg`, `assets/templates/marquee.svg` and `assets/templates/marquee-ambient.svg`, `assets/templates/chart.svg`, `assets/templates/bars.svg`, `assets/templates/flow.svg` (medium loop), `assets/templates/flow-long.svg` (storyboard) and `assets/templates/flow-short.svg` (one-shot), `assets/templates/loader.svg`, `assets/templates/typing.svg`, `assets/templates/divider.svg`, `assets/templates/badge.svg`, `assets/templates/timeline.svg`, `assets/templates/logos.svg`, `assets/templates/calendar.svg`, `assets/templates/ring.svg`.
