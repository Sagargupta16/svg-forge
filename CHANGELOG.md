# Changelog

All notable changes to this project are documented here. Follows [Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-10-18

### Added

- **Validator rule SV024**: a negative `width`, `height`, `r`, `rx` or `ry` on a shape, image, `use`, nested `svg`, pattern, mask, marker or filter is an error, since the element is not rendered.
- **Concepts before the storyboard**: the `animated-svg` workflow and the `svg-designer` agent offer two or three one-line concepts (the scene, what moves, what the resting frame shows), design the rest frame before any motion, and check the contact sheet at 240 px as well as full width. The agent gains an "If you catch yourself" table and asks the user to judge the loop.
- **`references/isometric.md`** in `animated-svg`: isometric line figures for hero and cover art: the 2:1 projection, solids as a silhouette and one crease, four stroke weights on a filled plate, a designed rest, one highlight, honest paint order, and the clock standing in for the pointer. Distilled for SMIL and CSS from the hairline project (MIT).
- Design rules shared across the skills: rest is designed, one highlight at a time, paint order is depth, hit areas do not move, two clocks (a tween for a choice, a spring for the pointer), and page-driven theming for inline files. `svg-audit` reviews the rest frame, the highlight count and the paint order.
- Rules from the portfolio covers this plugin grew out of: two loop shapes decided by what the frozen frame shows (build up over a static ghost layer to one `END`/`GONE` exit, or open on the finished state with a clear window), at least one beat that changes a state, state changes as stacked elements with an opacity window, the pop recipe, overlapping round trips for many-to-one reuse, a deployed app's scene keeps the UI skeleton and one signature control, text stand-ins are bars, the beat table lives at the top of the scene file, icon canvases use 6 px labels in an 80 px source scaled 1.5x to 1.8x, and verification notes on unfocused preview panes and still captures.
- `requirements-dev.txt` pins the development tools so Renovate tracks them; CI installs from it.

### Fixed

- `validate_svg.py` checks the `to`, `from`, `by` and `values` of SMIL animations that target `href` or `src`: an `<animate attributeName="href" to="https://...">` or a `<set>` to a `javascript:` URL passed with no finding. Tab, LF and CR inside a URL scheme are stripped before classifying, as browsers do, so `java&#10;script:` is SV006 under every target.
- `forge.py --kind flow` with more columns than its width can hold emitted negative-width rects and the nodes vanished; it now exits 2 with the width it needs.
- `forge.py --kind bars --height` packs the rows into the canvas instead of drawing past its bottom edge, and refuses a height that cannot hold the items.
- `forge.py --kind calendar` with a date in the first year exits 2 with a message instead of a traceback.
- `scripts/check.py` skips `.venv`, `venv` and `.tox`, so a contributor's virtual environment cannot turn the repo gate red.

### Changed

- `--width` and `--height` accept 8 to 4096 px, sharing the upper bound with `--size` (was 4000).
- forge.py takes its HLS, alpha and mix helpers from themes.py instead of keeping a second copy; output is byte-identical.
- CI runs the checks job on Python 3.15 and the tests on 3.12 to 3.15, with ruff 0.17.1.

## [0.2.0] - 2026-10-11

### Added

- **Any size for every kind**: `--size` takes `WxH`, a width or one of 15 presets (`readme`, `readme-half`, `card`, `og`, `banner-wide`, `linkedin-banner`, `youtube-banner`, `square`, `story`, `slide-16x9`, `icon-512`, `icon-128`, `icon-64`, `favicon-32`, `avatar-460`). New kinds lay out natively at the canvas; the ten existing kinds scale their layout in through the root viewBox, centered and never distorted. `sizes.py` adds a `Layout` scaling helper.
- **Themes**: 15 presets (GitHub, Nord, Dracula, Catppuccin Mocha and Latte, Tokyo Night, Gruvbox, Solarized dark and light, One Dark, high-contrast dark and light, transparent dark and light) with official sources, families with `--mode dark|light|both`, `auto:<hex>` themes built from one brand color, and palette JSON files that extend a preset (`assets/palettes/ember.json`, `paper.json`). `--accent` now defaults to the theme's own accent.
- **Contrast guarantee**: every theme keeps text at 4.5:1 and marks at 3:1 (WCAG 1.4.3 and 1.4.11); colors that fall short, including a custom accent, move to the nearest passing lightness and are reported on stderr.
- **Four new kinds**: `timeline` (career or history rail, `--variant vertical`), `logos` (logo wall of inline SVG, PNG/WebP data URIs or text pills; ambient timing makes it a marquee), `calendar` (53-week contribution heatmap with quartile levels, `--variant accent`) and `ring` (progress rings). They scale to any canvas with a 7 px font floor.
- **Flow text spec**: `--kind flow --data "push -> build -> unit, e2e -> deploy"`, with parallel steps, `-[label]->` edge labels, return arcs and `#` comments, inline or from a `.txt` file.
- **Validator contrast rules SV021-SV023** (WCAG 1.4.3 and 1.4.11), `--strict-contrast`, `--theme dark|light|both`, and per-element measurements in `stats.contrast` of `--json`.
- **`frames.py`**: renders an animated SVG's timeline into one PNG contact sheet. It detects the cycle from SMIL (including `a.end` chains) and CSS, puts t=0 and the loop seam on the same sheet, offers dark, light or both themes, and blocks scripts and network in each frame. Without a browser it writes only the HTML and exits 3. `scripts/preview.py --frames` writes one sheet per example.
- **`optimize_svg.py`**: stdlib, animation-safe minifier that re-validates (ids, animation inventory, no new errors) before writing. **`assets/svgo.config.mjs`**: SVGO v4 preset-default with 13 animation-breaking plugins off.
- **Requirements intake** in the `animated-svg` workflow and the `svg-designer` agent: where it is shown, size, theme, content and motion are pinned before drawing; both now verify with contrast and a contact sheet.
- **Evals**: a `claude plugin eval` suite (12 cases, fixtures, deterministic graders) and offline suite tests.

### Changed

- The repo's own gates validate with contrast on: `scripts/check.py` checks each shipped SVG (now including the README header in `docs/`) against the background it is shown on, and the forge tests check every kind, theme and size. Measured with the new rules, the 35 SVGs shipped in 0.1.0 had 17 contrast errors; the 50 shipped now have 0.
- Visible design changes from the contrast pass: the badge pill is opaque (its text cannot reach 4.5:1 on both GitHub pages otherwise), empty calendar days are an 8% tint, the timeline rail gaps at nodes come from a mask, and single-file divider and loader marks use a darker accent (`#60a5fa` becomes `#4696f9`).
- Templates and examples regenerated; 4 new templates and 11 new examples. The README header is now a recipe (`docs/hero.json`), so it regenerates and is checked like every other file.

### Known limits

- The ten scaled kinds keep their label sizes, so at icon presets their text is too small to read (flow at 128 px draws labels about 1.4 px tall). Use a native kind or a label-free mark for icons.

## [0.1.0] - 2026-10-10

### Added

- **Plugin manifest and self-hosted marketplace** (`.claude-plugin/`), so the repo installs with `/plugin marketplace add Sagargupta16/svg-forge`.
- **`animated-svg` skill**: self-contained animated SVGs for GitHub READMEs and `<img>` on the web. Workflow from target and timing preset to storyboard, generation, validation and safe optimization, with references on what GitHub's image proxy allows, a SMIL and CSS cookbook, timing, design, optimization, gotchas and accessibility.
- **`motion-scene` skill**: React + Motion scenes for apps (research, build, verify), with references on composition, motion, gotchas, primitives and verification, plus a copy-in TypeScript kit (tokens, timing, routes, primitives, near-viewport mount, freeze hook, an example scene).
- **`svg-audit` skill**: ranked findings for an existing SVG or scene; report first, fix on request.
- **`svg-designer` subagent**: studies the subject, storyboards, builds, validates and iterates.
- **`forge.py` generator**: kinds `tiles`, `hero`, `marquee`, `chart`, `bars`, `flow`, `loader`, `typing`, `divider`, `badge`; themes `dark`, `light`, `both` (with a `<picture>` snippet); timing presets `micro`, `short`, `medium`, `long`, `ambient`; deterministic, escaped, self-contained output.
- **`validate_svg.py` validator**: rule ids `SV0xx` for render-target safety, accessibility, ids, size and animation sanity.
- **Starter templates, an examples gallery, repo checks, tests and CI.**
