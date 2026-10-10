# Contributing to svg-forge

Thanks for helping. svg-forge is small on purpose: three skills, one subagent, a generator, a validator, starter files. Contributions that make graphics render more reliably or read better are the most welcome.

## Setup

```bash
git clone https://github.com/Sagargupta16/svg-forge
cd svg-forge
pip install ruff pytest
```

No other dependencies. The scripts use the Python 3.12+ standard library only.

## Before you open a PR

```bash
python scripts/check.py
python -m pytest -q
ruff check .
ruff format --check .
npx -y @sagargupta1610/skillcheck@0.2.5 lint skills
```

All five must pass. CI runs the same commands.

## Adding a generator kind or option

1. Add the kind to `skills/animated-svg/scripts/forge.py`: one function, the shared helpers, the timing preset table. Escape every interpolated string and keep output deterministic.
2. Add a test case in `tests/` (the meta-test fails if a kind has none) and a hostile-input case if the kind renders user text.
3. Regenerate its starter file in `skills/animated-svg/assets/templates/` and add a gallery row in `examples/README.md`.
4. Document the kind in `skills/animated-svg/SKILL.md`.
5. Look at the output in a browser, and on GitHub through a pushed branch if it targets READMEs.

## Adding a validator rule

Give it the next `SV0xx` id, a one-line message that says how to fix it, a fixture that triggers it and one that does not. Errors are for things that break rendering or safety; everything else is a warning.

## Skill and reference content

- Frontmatter: `name` equals the folder name; `description` is a `>-` folded block that says what the skill does and lists "Use when" triggers; no unquoted `: ` inside it.
- Keep `SKILL.md` under 500 lines; move depth into `references/` (one level deep, linked from `SKILL.md`).
- Every external claim about browser or GitHub behavior links its source.
- Write "the user", not a person's name. No absolute home paths.

## Style

- No en or em dash characters anywhere (use `-` or `--`). `scripts/check.py` fails on them.
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- CHANGELOG entries go under a concrete version (`## [0.2.0] - YYYY-MM-DD`), never "Unreleased". Releases bump the version in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
