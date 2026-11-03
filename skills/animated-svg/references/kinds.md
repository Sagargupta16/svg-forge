# Kinds and options

Every `forge.py` kind with what it draws, its default timing, its `--data` shape and what its phone layout does, then every option, packs and the starter templates. [SKILL.md](../SKILL.md) step 4 decides whether a kind fits; this is the lookup.

## Kinds

Stats and data:

| Kind | Draws | Default timing | `--data` shape | Phone (`--device phone`) |
| --- | --- | --- | --- | --- |
| `tiles` | stat tiles grid; looping turns it into a spotlight | short | `[{"value": "42", "label": "repos", "tone": "ok"}]` (up to 16), or `{"items": [...], "cols": 4, "title": "..."}` | 2 columns (1 when a value needs the width), values in full, labels wrap, "+N more" past 8 |
| `stats` | summary card: title, up to 6 rows of glyph, label and static value, and a grade ring that draws in | short | `{"title": "Open source stats", "rows": [{"label": "Stars earned", "value": "1.2k", "glyph": "star"}], "grade": {"label": "A+", "value": 0.86}}` (1 to 6 rows; glyph is a `GLYPHS` name and optional; grade optional, value 0 to 1; a bare list is the rows) | rows and grade ring side by side at 320, rows at full spacing |
| `streak` | total contributions, current streak in a ring under a flame, longest streak, each with its date range | short | `{"total": 1284, "total_range": "Oct 5, 2025 - Present", "current": 12, "current_range": "Sep 29 - Oct 10", "longest": 41, "longest_range": "Mar 2 - Apr 11"}` (ranges optional), or calendar data (`{"days": [...]}` or `{"start", "counts"}`): streaks counted with today allowed to be empty, broken only by an empty yesterday | current on top, total and longest side by side under it |
| `chart` | line chart that draws in, area, peak marker | short | `{"values": [120, 150, 190], "labels": ["W1", "W2", "W3"], "unit": "", "peak": "PEAK"}` (at least 2 values) | low and high ticks only, end labels share the axis, peak label kept inside |
| `bars` | labelled progress bars that grow | short | `{"items": [{"label": "Python", "value": 46}], "unit": "%"}`; optional `max` and `tone` per item (up to 12) | labels wrap beside their value, "+N more" past 8 |
| `breakdown` | parts of a whole: a stacked bar that grows in (`--variant donut` or `pie`, drawn by one clockwise sweep; the donut names its largest item) and a legend of swatch, label and percent; ten items by name, the rest as Other | short | `{"title": "Languages", "items": [{"label": "Python", "value": 46, "color": "#3572a5"}]}` or the bare list (percents to one decimal, summing to 100.0) | chart on top, legend in one or two columns under it |
| `radar` | 3 to 8 axes on one max: rings, spokes, labels with values; the value polygon grows from the center and its points pop in; an optional muted, dashed compare polygon with a key | short | `{"title": "Project health", "max": 100, "series": ["This release", "Last release"], "axes": [{"label": "Tests", "value": 84, "compare": 70}]}` or the bare axes list (`compare` on every axis or none) | side labels shortened, never overlapping |
| `ring` | progress rings that draw in to static values | short | `{"title": "Goals", "items": [{"label": "Coverage", "value": 91}, {"label": "Issues", "value": 42, "max": 60, "tone": "ok"}]}` | 3 or 2 per row, else one ring per row with its label beside it |
| `calendar` | 53-week contribution heatmap with quartile levels (`--variant accent` uses the accent ramp) | short | `{"days": [{"date": "2025-10-07", "count": 10}]}` or `{"start": "2025-10-05", "counts": [4, 0, 5]}` | the last 26 weeks, labels at 10.5 px |
| `skyline` | the contribution year as an isometric line city ([isometric.md](isometric.md)): one rounded block per day on a base slab, height by quartile level, the busiest day lit and a little taller; depth bands rise in oldest first, the lit edge pulses on loops (`--variant accent`) | short | the calendar shape | the last 26 weeks at the year's levels |

Headers, cards and identity:

| Kind | Draws | Default timing | `--data` shape | Phone |
| --- | --- | --- | --- | --- |
| `hero` | title, rotating taglines, status pill, node constellation | long | `{"title": "Name", "kicker": "Hi", "taglines": ["One", "Two"], "status": "Live", "meta": "MIT", "nodes": ["api", "cli"]}` (up to 6 taglines; up to 8 nodes of 8 chars, shown when the canvas is at least 560 wide) | one column: title shrinks then wraps whole, taglines wrap to 2 lines, pill and meta on rows of their own, no constellation |
| `banner` | header or footer banner: kicker, title, and lines that take turns over a drifting shape (`--variant wave`, `waving`, `slice`, `rounded`, `cylinder`, `speech`); the shape hugs the top of a header and the bottom of a footer | long | `{"kicker": "Open source", "title": "Northwind", "subtitle": "Inventory for small shops", "lines": ["Works offline", "MIT licensed"], "section": "header"}` (a bare string is the title, a bare list the lines; up to 6 lines; with no title the lines take its place) | title and subtitle wrap to 2 lines |
| `heading` | numbered section header: number eyebrow, title, an accent rule that draws in, on the theme bg with no border; ship with `--theme both` | medium | `{"number": "01", "title": "Projects", "subtitle": "What ships next"}` or a bare title string (an integer number is zero-padded) | eyebrow and title wrap to 2 lines each |
| `card` | project or repo card: date, live or source status, title, a 3-line summary, tag chips with "+N more", language dot, stars and forks, a shine sweep; 410 by 196, so two sit side by side | medium | `{"title": "Northwind", "description": "...", "status": "live", "date": "Mar 2026", "language": "Python", "stars": 1240, "forks": 86, "tags": ["python", "postgres"]}` (title required) | same card at 320 |
| `quote` | quote card: a large quote mark, the quote wrapped to 5 lines, the author; up to 6 quotes take turns, a single one fades in | long | `{"text": "...", "author": "..."}` or `{"quotes": [{"text", "author"}, ...]}` (a bare list or string works) | quote at 14 px or more, author at 10.5 |
| `badge` | label and value pill with a status dot and shine | medium | `{"label": "build", "value": "passing", "tone": "ok", "dot": true}` | none: a content-sized pill reads at its own size |
| `logos` | logo wall; `--timing ambient` turns it into a marquee | short | `{"title": "Trusted by", "items": [{"label": "Acme", "svg": "logos/acme.svg", "color": "#38bdf8"}, {"label": "Ember", "image": "logos/ember.png"}, {"label": "Text only"}]}` (SVGs inline with prefixed ids, PNG/WebP up to 64 KB as data URIs, a bare label is a text pill; paths from the working directory) | 2 columns of pills, "+N more" past 6 rows |
| `marquee` | text chips scrolling at constant px/s | ambient | `["python", "rust"]` or `{"rows": [["a", "b"], ["c", "d"]]}` (up to 3 rows, alternating direction) | same strip at 320 |
| `divider` | hairline with a center dot and a pulse | medium | none; transparent, so use `--theme both` | none: no text |

Diagrams and stories:

| Kind | Draws | Default timing | `--data` shape | Phone |
| --- | --- | --- | --- | --- |
| `flow` | nodes and edges with packets: pipeline or architecture | medium | `{"nodes": ["commit", {"id": "deploy", "tone": "ok"}], "edges": [["commit", "deploy"]]}` (2-12 nodes in flow order; an edge back to an earlier node is a return arc), or a text spec, inline or a `.txt` file: `push -> build -> unit, e2e -> deploy` (comma = parallel, `-[label]->` labels an edge, newline or `;` between statements, `#` comments) | keeps its columns when labels fit at 10.5 px, else top to bottom with return arcs down the right |
| `timeline` | career or history rail that draws in; the current item pulses (`--variant vertical` for a column) | long | `{"title": "Career", "items": [{"start": "2019", "end": "2022", "title": "Senior engineer", "subtitle": "Search"}, {"start": "2024", "title": "Lead", "current": true}]}` (up to 12 items; only an item marked `"current": true` pulses, and without an `end` it reads "start - now") | always vertical; titles and subtitles wrap to 2 lines |
| `typing` | terminal that types commands, then shows output | long | `{"title": "bash", "prompt": "$", "lines": [{"cmd": "make build", "out": ["done"], "tone": "ok"}]}` (up to 8 lines) | long commands and output wrap; the window grows taller |

Small marks:

| Kind | Draws | Default timing | `--data` shape | Phone |
| --- | --- | --- | --- | --- |
| `loader` | `--variant` spinner, dots, bar, pulse, orbit, bars, wave, ring, blocks, clock or bounce; loops unless `--once` | medium | none; one turn is 0.6 / 0.9 / 1.2 / 2.0 / 4.0 s for micro / short / medium / long / ambient | none: no text |

`tone` is `accent` (default), `ok`, `warn`, `muted` or a hex color. `glyph` names a small line icon drawn for the generator: star, fork, commit, pull, issue, flame, check, clock, eye, code, repo, calendar, trophy, heart, bolt.

## Options

- `--kind KIND` (required), `--out FILE` (omit to print one theme to stdout).
- `--device desktop|phone|both`: `phone` draws the 320 px phone layout with no text under 10.5 px; `both` writes `NAME.svg` and `NAME-mobile.svg` and prints the `<picture>` whose `<img>` is the phone file and whose `(min-width: 1012px)` source swaps in the desktop one ([github-readme.md](github-readme.md) section 3b). With `--theme both` that is four files and four sources. On a phone a fixed `--height` is a minimum for tiles, bars and hero, and a height too short for flow, timeline or ring is an error. `--device phone` and `--size` do not mix.
- `--size`: `WxH`, a width, or a preset (`readme`, `card`, `og`, `linkedin-banner`, `square`, `story`, `icon-128` and more). The native kinds (banner, heading, stats, streak, breakdown, radar, card, quote, skyline, timeline, logos, calendar, ring) lay out at the canvas; the other ten scale their layout in, centered and never distorted, but their labels do not grow, so keep icon sizes to native kinds or marks. Use it or `--width`/`--height` (8 to 4096), not both.
- `--theme`: `dark` (default), `light`, `both` (the GitHub pair), a preset (`nord`, `dracula`, `catppuccin-mocha`, `tokyo-night`, ...), a family, `auto:<hex>` for a brand color, or a palette `.json`. `--mode dark|light|both` picks a family's variant; `both` needs `--out`, writes `NAME-dark.svg` and `NAME-light.svg` and prints a `<picture>` snippet with the paths as given, so pass a repo-relative `--out`.
- `--accent "#rrggbb"` (default: the theme's own). Text reaches 4.5:1 and marks 3:1 in every theme; a color that falls short, your accent included, moves to the nearest passing lightness and is noted on stderr.
- Every preset, the native and scaled kinds, palette files and the contrast rules: [themes-and-sizes.md](themes-and-sizes.md).
- `--timing micro|short|medium|long|ambient` (kind default otherwise); `--loop` or `--once` overrides looping; `--speed` sets px/s for marquee and ambient (default 40).
- `--title` (visible heading where the kind has one, and the `<title>`), `--desc` (overrides the generated `<desc>`).
- `--data` inline JSON or a path to a JSON file. Prefer a file on Windows shells, where inline JSON quoting differs.
- `--variant` (loader, banner, breakdown, timeline, calendar, skyline; see the tables), `--reduced-motion ignore|respect` (default `ignore`; kinds move mostly through SMIL, so `respect` freezes only their CSS parts, see [timing.md](timing.md) section 7), `--font-stack sans|mono|serif|system` or a font-family list, `--id-prefix` (default: a hash of the input, so ids and classes never collide when files are inlined together).

```bash
python scripts/forge.py --kind flow --timing long --data pipeline.json --out assets/flow.svg
python scripts/forge.py --kind stats --theme both --device both --data stats.json --out assets/stats.svg
python scripts/forge.py --kind breakdown --variant donut --data languages.json --out assets/langs.svg
python scripts/forge.py --kind banner --variant waving --data banner.json --out assets/banner.svg
python scripts/forge.py --kind loader --variant orbit --once --out assets/orbit.svg
python scripts/forge.py --kind skyline --theme both --data contributions.json --out assets/year.svg
```

Output is deterministic (same input, same bytes, LF) and a file is rewritten only when its bytes change, so scheduled runs commit nothing on a quiet day. Bad options or data exit with status 2 and a message.

## Packs: a whole README in one file

`scripts/pack.py PACK.json [--out-dir DIR] [--check]` renders a matching set of cards (one theme, accent and device set) and writes `snippet.md` with every card's `<picture>` markup in order: links wrap the picture, the pack's alt text (required) replaces the title, cards that share a `row` sit in one `<p align="center">`, and every image sets only its width. A pack card gives the same bytes as the matching `forge.py` command. `--check` exits 1 when a file on disk is stale or missing, and a bad pack exits 2 naming the card and the field.

```json
{
  "theme": "both",
  "accent": "#38bdf8",
  "device": "both",
  "out_dir": "assets/cards",
  "cards": [
    {"name": "hero", "kind": "hero", "alt": "Northwind Labs: developer tools for cloud teams",
     "data": {"title": "Northwind Labs", "taglines": ["Developer tools for cloud teams"]}},
    {"name": "license", "kind": "badge", "row": "badges", "alt": "License: MIT",
     "link": "LICENSE", "data": {"label": "license", "value": "MIT"}}
  ]
}
```

Any `forge.py` option goes on a card under its flag name with underscores (`timing`, `variant`, `size`, `font_stack`, ...), and a card may override the pack's `theme`, `accent` and `device`. Paths resolve from the pack's folder. Starter packs: [assets/packs/profile.json](../assets/packs/profile.json) (hero, numbered headings, stats, streak, languages, tiles, timeline, stack strip, wave footer) and [assets/packs/project.json](../assets/packs/project.json) (header banner, a linked badge row, quickstart terminal, pipeline, downloads chart, languages). Copy one next to your README and edit the data.

## Starter templates

Every file passes the validator: `assets/templates/<kind>.svg` for each of the 23 kinds, plus `hero-light.svg`, `marquee-ambient.svg`, `flow-long.svg` (storyboard) and `flow-short.svg` (one-shot).
