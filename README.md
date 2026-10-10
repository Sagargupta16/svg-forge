<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/hero-light.svg">
  <img alt="svg-forge: animated SVGs that survive GitHub's image proxy" src="docs/hero-dark.svg" width="100%">
</picture>

[![CI](https://github.com/Sagargupta16/svg-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/Sagargupta16/svg-forge/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-0.1.0-2563eb)
![License](https://img.shields.io/badge/license-MIT-2563eb)

</div>

A Claude Code plugin for designing animated SVGs that look deliberate and render everywhere they are shown: self-contained files for GitHub READMEs and `<img>` tags, and React + Motion scenes for web apps. The header above was made with it.

It packages what actually worked (and what broke) while building animated README cards, project cover scenes and diagrams: the rules, the gotchas with their fixes, a generator, and a validator that catches the mistakes that make an SVG silently stop animating.

## Install

```
/plugin marketplace add Sagargupta16/svg-forge
/plugin install svg-forge@svg-forge
```

The generator and validator are plain Python 3.12+ scripts with no dependencies, so they also work without Claude Code.

## What's inside

| Part | Use it for |
| --- | --- |
| [`animated-svg`](skills/animated-svg/SKILL.md) skill | Standalone `.svg` files: README headers and stat cards, diagrams, loaders, badges, marquees. Covers what GitHub's image proxy allows, a SMIL and CSS cookbook, timing, design, safe optimization, gotchas and accessibility. |
| [`motion-scene`](skills/motion-scene/SKILL.md) skill | Animated illustrations inside a React app with Motion: cover art, card scenes, mechanism diagrams. Research, build and verify modes, plus a copy-in TypeScript kit. |
| [`svg-audit`](skills/svg-audit/SKILL.md) skill | Ranked findings for an existing SVG or scene: render-target safety, accessibility, motion quality, weight. Reports first, fixes on request. |
| [`svg-designer`](agents/svg-designer.md) agent | End to end: studies the subject, storyboards, builds, validates and iterates until it reads at the size it is shown. |
| [`forge.py`](skills/animated-svg/scripts/forge.py) | Generator: 10 kinds x 3 themes x 5 timing presets, deterministic and escaped output. |
| [`validate_svg.py`](skills/animated-svg/scripts/validate_svg.py) | Validator: rules SV001 to SV020 for GitHub safety, accessibility, ids, size and animation sanity. |

Ask Claude for "an animated header for my README" or "a cover scene that shows how this tool works", or run the scripts directly:

```bash
python skills/animated-svg/scripts/forge.py --kind flow --timing long \
  --data examples/data/pipeline.json --out pipeline.svg
python skills/animated-svg/scripts/validate_svg.py pipeline.svg --target standalone
```

## Timing presets

| Preset | Length | For |
| --- | --- | --- |
| `micro` | 120 to 300 ms, once | hover, press and toggle feedback |
| `short` | 0.4 to 1.2 s, once | staggered entrances that hold their final frame |
| `medium` | 3 to 6 s loop | mechanism scenes, pulses, packets on a path (default) |
| `long` | 8 to 20 s loop | storyboards of 3 to 6 beats on one shared clock |
| `ambient` | set by speed (px/s) | slow drift and marquees |

Entrances are poster-safe: an SVG's static attributes hold the finished frame, so link previews and PNG exports never show blank tiles. Motion is on by default; `--reduced-motion respect` adds an opt-in `prefers-reduced-motion` block for CSS animations.

## Gallery

Every example is generated and reproducible byte for byte; the commands are in [examples/README.md](examples/README.md).

| | |
| --- | --- |
| <img src="examples/flow-storyboard.svg" alt="flow, long storyboard"> | <img src="examples/tiles-spotlight.svg" alt="tiles with a spotlight"> |
| `flow`, long: 8-beat storyboard with a return arc | `tiles`, medium: spotlight cycling the tiles |
| <img src="examples/chart-loop.svg" alt="chart that draws in"> | <img src="examples/marquee-rows.svg" alt="two marquee rows"> |
| `chart`, medium: draws, holds, fades, repeats | `marquee`, ambient: two rows in opposite directions |
| <img src="examples/typing-medium.svg" alt="typing terminal"> | <img src="examples/bars-loop.svg" alt="bars that grow"> |
| `typing`, medium: terminal lines | `bars`, long: value and max labels |

Starter files for every kind live in [skills/animated-svg/assets/templates/](skills/animated-svg/assets/templates/). `python scripts/preview.py` builds a local gallery of everything on GitHub's dark and light backgrounds.

## What GitHub allows, in one paragraph

GitHub sanitizes inline `<svg>` in Markdown, so an SVG animates only when it is referenced as an image. Through the image proxy, inline `<style>`, CSS `@keyframes`, SMIL and `data:` URIs work; scripts, `<foreignObject>`, external fonts and external images do not. `prefers-color-scheme` inside the file follows the OS rather than GitHub's theme and fails on WebKit, so ship a `<picture>` pair (`forge.py --theme both` prints the snippet). Sources and the rest of the rules are in [github-readme.md](skills/animated-svg/references/github-readme.md).

## Development

```bash
python scripts/check.py
python -m pytest -q
ruff check .
ruff format --check .
npx -y @sagargupta1610/skillcheck@0.2.5 lint skills
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for adding a kind, a validator rule or skill content, and [SECURITY.md](SECURITY.md) for reporting issues.

## License

[MIT](LICENSE)
