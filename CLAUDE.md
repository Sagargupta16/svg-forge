# CLAUDE.md

> This file stacks on top of the workspace root at `C:\Code\GitHub\`:
> - Root [`CLAUDE.md`](../../CLAUDE.md) -- voice, rules, routing map, references, skills, slash commands, conventions.
> - Root [`MEMORY.md`](../../MEMORY.md) -- live facts across repos.
> - Root [`STATUS.md`](../../STATUS.md) -- live PR/CI/security dashboard.
> - [`.claude/resources/`](../../.claude/resources/README.md) -- deep reference for collaboration, workflow, git, OSS, debugging, voice.
>
> Read those first. The guidance below only adds **repo-specific context** -- it does not override anything in the root.

## Project

Public Claude Code plugin (`svg-forge`) for designing animated SVGs that render everywhere: self-contained files for GitHub READMEs and `<img>`, and React + Motion scenes for web apps. Built from what worked (and broke) in the owner's portfolio covers, profile README renderer and README card actions.

Installed with `/plugin marketplace add Sagargupta16/svg-forge` then `/plugin install svg-forge@svg-forge`.

## Stack

- **Language**: Python 3.12+ standard library (generator, validator, repo checks); TypeScript + React 19 + Motion for the copy-in scene kit
- **Framework**: none at runtime; the plugin is Markdown skills, one subagent, scripts and starter files
- **Database**: none
- **Package manager**: none required; `pip install ruff pytest` for development
- **Deploy target**: GitHub repo + self-hosted plugin marketplace (`.claude-plugin/marketplace.json`, `source: "./"`)

## Run

```
python skills/animated-svg/scripts/forge.py --kind hero --title "Hello" --out hero.svg
python skills/animated-svg/scripts/validate_svg.py hero.svg --target standalone
python scripts/preview.py
python scripts/preview.py --rebuild   # regenerate every template, example and examples/README.md from the recipe table
```

## Test

```
python scripts/check.py
python -m pytest -q
ruff check .
ruff format --check .
npx -y @sagargupta1610/skillcheck@0.2.5 lint skills
```

## Entry points

- `skills/animated-svg/SKILL.md` -- standalone SVG files (README cards, banners, loaders, icons, diagrams)
- `skills/motion-scene/SKILL.md` -- React + Motion scenes for apps
- `skills/svg-audit/SKILL.md` -- audit an existing SVG or scene, report first, fix on request
- `agents/svg-designer.md` -- subagent that storyboards, builds, validates and iterates
- `skills/animated-svg/scripts/forge.py` -- generator CLI (kinds x themes x timing presets)
- `skills/animated-svg/scripts/validate_svg.py` -- validator CLI (rule ids SV0xx)

## Key files

- `skills/animated-svg/scripts/forge.py` -- the generator; templates under `assets/templates/` are its output, regenerate them instead of hand-editing
- `scripts/check.py` -- repo gate CI runs first (dashes, secrets, home paths, frontmatter, links, manifests, every shipped SVG validates)
- `.claude-plugin/plugin.json` + `marketplace.json` -- versions must match

## Gotchas

- Inline SVG in GitHub Markdown is sanitized away; only SVG referenced as an image animates. Test README output on a pushed branch, not in a local Markdown preview.
- In-SVG `prefers-color-scheme` follows the OS, not GitHub's theme, and fails on WebKit. Ship `<picture>` pairs for dark and light.
- SVGO's default preset breaks animations (cleanupIds, removeHiddenElems, removeUselessDefs...). Use the safe config in `skills/animated-svg/references/optimize.md`.
- `.gitattributes` forces LF; generator output must be byte-identical across runs (tests check it).

## Repo-specific rules

- Everything here is public: no personal names in skill bodies (say "the user"), no home paths, no private project names. Author/owner fields are the exception.
- Motion stays visible by default. `forge.py --reduced-motion` defaults to `ignore`; `respect` is an opt-in for users who want it. Never add a reduced-motion gate to an app that has its own motion control.
- Skill frontmatter: `name` equals the folder, `description` is a `>-` folded block with "Use when" triggers and no unquoted `: `. skillcheck must report 0 errors.
- Every PR updates CHANGELOG.md under a concrete version and bumps both manifests when it releases.
- No en or em dashes anywhere, including SVG text; `scripts/check.py` fails on them.
