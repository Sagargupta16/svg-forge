# Themes and sizes

How `forge.py` picks colors and a canvas: theme presets and families, brand themes, palette files, the contrast guarantee, size presets, and which kinds lay out natively versus scale. `scripts/themes.py --list` and `scripts/sizes.py --list` print the live tables.

## 1. Themes

| `--theme` value | Means |
| --- | --- |
| `dark` (default), `light` | GitHub's dark (`#0d1117`) or light (`#ffffff`) page colors |
| `both` | the GitHub pair: writes `NAME-dark.svg` and `NAME-light.svg` and prints a `<picture>` snippet |
| a preset | `github-dark`, `github-light`, `nord`, `dracula`, `catppuccin-mocha`, `catppuccin-latte`, `tokyo-night`, `gruvbox-dark`, `solarized-dark`, `solarized-light`, `one-dark`, `high-contrast-dark`, `high-contrast-light`, `transparent-dark`, `transparent-light` |
| a family | `github`, `catppuccin`, `solarized`, `high-contrast`, `transparent`; gives the dark variant unless `--mode` says otherwise |
| `auto:<hex>` or `#hex` | a theme built from one brand color, with both variants |
| a `.json` path | a palette file that extends a preset; see `assets/palettes/ember.json` and `assets/palettes/paper.json` |

- `--mode dark|light` picks a family's (or brand theme's) variant. `--mode both` writes the pair and prints the snippet; it needs `--out`, and the snippet uses the paths exactly as given, so pass a repo-relative path such as `--out assets/hero.svg`.
- Impossible combinations exit 2 with a message: a variant that does not exist (`--theme nord --mode light`), `--theme dark --mode light`, `--theme both --mode dark`, a pair without `--out`, an unknown theme.
- Transparent themes draw a border and no background, so the page shows through. They suit a file that must sit on any page; use a pair when the text matters.
- `--accent` defaults to the theme's own accent; an explicit `--accent` wins.

Palette JSON: `extends` (a preset name), any theme tokens to override at the top level (`bg`, `wash`, `card`, `ink`, `text`, `dim`, `muted`, `ok`, `warn`, `border`, `panel`, `panel_stroke`, `grid`), and optionally `accent`, `mode`, `transparent`, `name`, `description`. Tokens it leaves out come from the preset it extends.

## 2. The contrast guarantee

- Text tokens (`ink`, `text`) reach 4.5:1 on the background and on cards (WCAG 1.4.3).
- Labels, status colors and the accent used as a mark (`dim`, `ok`, `warn`, `muted`) reach 3:1 (WCAG 1.4.11); accent-colored small text is held to 4.5:1 on the surface it actually sits on.
- A color that falls short, including a custom `--accent`, moves by the smallest lightness step that passes. Each change is printed on stderr as a note, for example `nord: muted #a5abb6 -> #a8aeb8 as text, to reach 4.5:1`.
- Single files with no theme pair (badge, divider, loader by default) pick marks that reach 3:1 on both GitHub pages; text cannot reach 4.5:1 on both (the ceiling is about 4.35:1), which is why the badge pill is opaque.
- The validator measures the same rules (SV021-SV023); `check.py` runs them as errors on every shipped file.

## 3. Sizes

`--size` takes `WxH` (`1280x640`), a width (the kind's aspect gives the height) or a preset:

| Preset | Size | For |
| --- | --- | --- |
| `readme` | 880 wide | full-width README image |
| `readme-half` | 430 wide | two README images side by side |
| `card` | 400x200 | small stat or link card |
| `og` | 1280x640 | GitHub repository social preview |
| `banner-wide` | 1500x500 | X (Twitter) profile header |
| `linkedin-banner` | 1584x396 | LinkedIn profile background |
| `youtube-banner` | 2560x1440 | YouTube channel banner; keep text inside the safe area |
| `square` | 1080x1080 | square social post |
| `story` | 1080x1920 | 9:16 story or reel cover |
| `slide-16x9` | 1920x1080 | slide or video frame |
| `icon-512`, `icon-128`, `icon-64`, `favicon-32` | square | app, store, list and favicon icons |
| `avatar-460` | 460x460 | profile picture |

Use either `--size` or `--width`/`--height`, not both.

### Native and scaled kinds

- **Native** (`timeline`, `logos`, `calendar`, `ring`): lay out at the canvas, with fonts and spacing from `sizes.Layout` and a 7 px font floor.
- **Scaled** (`tiles`, `hero`, `marquee`, `chart`, `bars`, `flow`, `loader`, `typing`, `divider`, `badge`): draw their own layout, grown toward the canvas shape up to a per-kind limit, then fit in through the root `viewBox` with `preserveAspectRatio="xMidYMid meet"`, centered and never distorted. The margin takes the theme background, except badge, divider, loader and transparent themes.
- Scaled kinds keep their label sizes, so at icon presets their text is too small to read (flow at 128 px draws labels about 1.4 px tall). For icons, use a native kind or a mark without labels.
- At any size, check what a phone shows: an 880 px README image renders at about 0.41x at 375 px wide, so text that must be read needs about 22-24 px drawn size ([github-readme.md](github-readme.md)).
