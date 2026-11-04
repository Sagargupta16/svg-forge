# CLAUDE.md

> This file stacks on top of the workspace root at `C:\Code\GitHub\`:
> - Root [`CLAUDE.md`](../../CLAUDE.md) -- voice, rules, routing map, references, skills, slash commands, conventions.
> - Root [`MEMORY.md`](../../MEMORY.md) -- live facts across repos.
> - Root [`STATUS.md`](../../STATUS.md) -- live PR/CI/security dashboard.
> - [`.claude/resources/`](../../.claude/resources/README.md) -- deep reference for collaboration, workflow, git, OSS, debugging, voice.
>
> Read those first. The guidance below only adds **repo-specific context** -- it does not override anything in the root.

## Project

Public Claude Code plugin (`svg-forge`) for designing animated SVGs that render everywhere: self-contained files for any web page, app, docs site or GitHub README (anything that shows an `<img>`), poster PNGs for slides, email and link previews, and React + Motion scenes for web apps. GitHub is one target, not the scope. Built from what worked (and broke) in the owner's portfolio covers, profile README renderer and README card actions.

Installed with `/plugin marketplace add Sagargupta16/svg-forge` then `/plugin install svg-forge@svg-forge`.

## Stack

- **Language**: Python 3.12+ standard library (generator, validator, repo checks); TypeScript + React 19 + Motion for the copy-in scene kit
- **Framework**: none at runtime; the plugin is Markdown skills, one subagent, scripts and starter files
- **Database**: none
- **Package manager**: none required; `pip install -r requirements-dev.txt` for development
- **Deploy target**: GitHub repo + self-hosted plugin marketplace (`.claude-plugin/marketplace.json`, `source: "./"`)

## Run

```
python skills/animated-svg/scripts/forge.py --kind hero --title "Hello" --out hero.svg
python skills/animated-svg/scripts/forge.py --kind ring --theme nord --size og --out ring.svg
python skills/animated-svg/scripts/validate_svg.py hero.svg --target standalone --strict-contrast
python skills/animated-svg/scripts/forge.py --kind stats --theme both --device both --out assets/stats.svg   # desktop and phone, dark and light
python skills/animated-svg/scripts/pack.py skills/animated-svg/assets/packs/profile.json --out-dir preview/pack   # a whole README
python skills/animated-svg/scripts/frames.py hero.svg   # PNG contact sheet of the timeline (needs Chrome, Edge or Chromium)
python scripts/preview.py
python scripts/preview.py --rebuild   # regenerate every template, example and examples/README.md from the recipe table
python scripts/preview.py --frames    # contact sheet per example into preview/
```

## Test

```
python scripts/check.py
python -m pytest -q
ruff check .
ruff format --check .
npx -y @sagargupta1610/skillcheck@0.2.5 lint skills
claude plugin eval . --scaffold --allow-tools Write Edit   # real-model eval suite in evals/; costs money, run on request
```

## Entry points

- `skills/animated-svg/SKILL.md` -- standalone SVG files for pages, apps and READMEs (cards, banners, loaders, icons, diagrams)
- `skills/motion-scene/SKILL.md` -- React + Motion scenes for apps
- `skills/svg-audit/SKILL.md` -- audit an existing SVG or scene, report first, fix on request
- `agents/svg-designer.md` -- subagent that storyboards, builds, validates and iterates
- `skills/animated-svg/scripts/forge.py` -- generator CLI (23 kinds x any `--size` x theme presets x timing presets, `--device desktop|phone|both`)
- `skills/animated-svg/scripts/themes.py`, `sizes.py` -- theme presets with the contrast guarantee, size presets and `Layout`
- `skills/animated-svg/scripts/validate_svg.py` -- validator CLI (rule ids SV001-SV024, contrast SV021-SV023)
- `skills/animated-svg/scripts/pack.py` -- a pack JSON (`assets/packs/`) to a set of cards plus `snippet.md`
- `skills/animated-svg/scripts/frames.py`, `optimize_svg.py` -- timeline contact sheets and `--poster` PNGs, animation-safe minifier

## Key files

- `skills/animated-svg/scripts/forge.py` -- the generator; templates under `assets/templates/` are its output, regenerate them instead of hand-editing
- `scripts/check.py` -- repo gate CI runs first (dashes, secrets, home paths, frontmatter, links, manifests, every shipped SVG validates)
- `.claude-plugin/plugin.json` + `marketplace.json` -- versions must match

## Gotchas

- Inline SVG in GitHub Markdown is sanitized away; only SVG referenced as an image animates. Test README output on a pushed branch, not in a local Markdown preview.
- In-SVG `prefers-color-scheme` follows the OS, not GitHub's theme, and fails on WebKit. Ship `<picture>` pairs for dark and light.
- SVGO's default preset breaks animations (cleanupIds, removeHiddenElems, removeUselessDefs...). Use `optimize_svg.py` or `skills/animated-svg/assets/svgo.config.mjs`.
- Headless Chrome follows the OS reduced-motion setting, which is on for the owner; `frames.py` passes `--force-prefers-no-reduced-motion`, keep it.
- Contrast is a gate: a forge color change must be fixed in forge.py or themes.py (then `preview.py --rebuild`), never by editing generated SVGs.
- `.gitattributes` forces LF; generator output must be byte-identical across runs (tests check it).
- Desktop bytes do not depend on `--device`. To ship a phone file, add `--device both` to the existing recipe in `scripts/preview.py`; a second recipe would duplicate the desktop file.
- `examples/` has a 600 KB budget (a test checks it); fold a new phone file into an existing recipe before adding an example.

## Repo-specific rules

- Everything here is public: no personal names in skill bodies (say "the user"), no home paths, no private project names. Author/owner fields are the exception.
- Motion stays visible by default. `forge.py --reduced-motion` defaults to `ignore`; `respect` is an opt-in for users who want it. Never add a reduced-motion gate to an app that has its own motion control.
- Skill frontmatter: `name` equals the folder, `description` is a `>-` folded block with "Use when" triggers and no unquoted `: `. skillcheck must report 0 errors.
- Every PR updates CHANGELOG.md under a concrete version and bumps both manifests when it releases.
- No en or em dashes anywhere, including SVG text; `scripts/check.py` fails on them.
