# Changelog

All notable changes to this project are documented here. Follows [Semantic Versioning](https://semver.org/).

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
