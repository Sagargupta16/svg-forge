# Optimize safely

Make animated files small without breaking them: an animation-safe SVGO v4 config, id prefixing for inlined icons, size budgets and deterministic output.

## 1. When to optimize

- `forge.py` output is already compact and deterministic. Do not run any optimizer on it; change the generator or its input instead of the output.
- For artwork exported from design tools (Figma, Illustrator, Inkscape), which carries metadata, editor namespaces and long decimals, start with `scripts/optimize_svg.py`: standard library only, and it refuses to write a result that loses an id or an animation or adds a validator error. On an Inkscape-style file it saved 48.5%.
- Reach for SVGO with the config below only when you need more bytes than that.
- Always re-run `validate_svg.py` after optimizing, and look at the file again ([SKILL.md](../SKILL.md) step 6).

```bash
python scripts/optimize_svg.py in.svg --out out.svg   # or --in-place; --check reports without writing
python scripts/optimize_svg.py in.svg --out out.svg --precision 2
```

## 2. SVGO v4 config for animated files

SVGO v4.1.0 is current (2026-08-24). v4 dropped `removeViewBox` and `removeTitle` from `preset-default` and renamed `removeScriptElement` to `removeScripts`. Source: https://svgo.dev/docs/migrations/migration-from-v3-to-v4/

The config ships as [assets/svgo.config.mjs](../assets/svgo.config.mjs), with the reason for each plugin in its comments. It keeps every shipped example byte-identical in rendered frames and saves about 5%; SVGO's default preset broke all of them (it strips `role="img"`, deletes `opacity="0"` motion dots and drops the `<title>`/`<desc>` ids).

```js
// assets/svgo.config.mjs (comments trimmed)
export default {
  multipass: true,
  plugins: [
    {
      name: "preset-default",
      params: {
        overrides: {
          cleanupIds: false,
          removeHiddenElems: false,
          removeUselessDefs: false,
          moveGroupAttrsToElems: false,
          removeUselessStrokeAndFill: false,
          convertShapeToPath: false,
          removeUnknownsAndDefaults: false,
          convertEllipseToCircle: false,
          moveElemsAttrsToGroup: false,
          collapseGroups: false,
          mergePaths: false,
          inlineStyles: false,
          removeDesc: false,
        },
      },
    },
  ],
};
```

```bash
npx -y svgo@4 --config assets/svgo.config.mjs in.svg -o out.svg
python scripts/validate_svg.py out.svg --target standalone
```

Why each plugin is off:

| Plugin | What breaks | Source |
| --- | --- | --- |
| `cleanupIds` | Rewrites ids. It backs off when the file has `<style>` or `<script>`, so SMIL-only files still get rewritten; its `begin` handling may keep only the first id of `begin="a.end;b.end"` (read from source, untested). | https://svgo.dev/docs/plugins/cleanupIds/ |
| `removeHiddenElems` | Deletes `opacity="0"` elements, which are the start state of every fade-in. | https://svgo.dev/docs/plugins/removeHiddenElems/ |
| `removeUselessDefs` | Drops defs that animations or `<use>` still need. | https://github.com/svg/svgo/issues/2290 |
| `moveGroupAttrsToElems` | Moves a group's `transform` onto children, which breaks group-level `animateTransform` and CSS transforms. | https://github.com/svg/svgo/issues/1437 |
| `removeUselessStrokeAndFill` | Removes strokes that are invisible at rest but drawn by animation. | https://github.com/svg/svgo/issues/1677 |
| `convertShapeToPath` | Turns `<rect>`/`<circle>` into `<path>`, so `<animate attributeName="r">` or `width` target an attribute that no longer exists. | https://github.com/svg/svgo/issues/1634 |
| `removeUnknownsAndDefaults` | Strips `href` from `<animate>` elements that target another element, and `role="img"` from the root (seen with svgo 4.1.0). | https://github.com/svg/svgo/issues/2061 |
| `convertEllipseToCircle` | Same failure as `convertShapeToPath` for `attributeName="rx"` or `"ry"`. | precaution |
| `moveElemsAttrsToGroup` | In a file without `<style>`, hoists a transform the children share onto the group; a child's own `animateTransform` then no longer replaces it. | precaution |
| `mergePaths` | Joins sibling paths with equal attributes, so a shared line-draw class dashes one combined path and `nth-child` staggers shift. | precaution |
| `removeDesc` | Keeps the `<desc>` that `aria-labelledby` points at ([accessibility.md](accessibility.md)). | precaution |
| `inlineStyles` | Moves `.x { animation: ... }` into a `style` attribute, which then outranks the `@media (prefers-reduced-motion)` block. | precaution |
| `collapseGroups` | Folds a positioning `<g transform>` into a child that CSS animates; the CSS `transform` then replaces it. | precaution |

Also off for path morphs that interpolate from the base `d` (a `to=` morph rather than a `values` list): `convertPathData`, because it may rewrite the base path into different commands than the target. Morphs written with a full `values` list are unaffected.

Check that nothing was lost:

```bash
for f in in.svg out.svg; do grep -oE '<(animate|animateTransform|animateMotion|set)\b|@keyframes' "$f" | sort | uniq -c; done
```

The counts must match, and the file must look the same at a few seeked frames.

## 3. Prefix ids when inlining icons or files

Ids are global to the document. Two inlined icons that both define `id="a"` render with whichever gradient came first, and an SVG inlined into a page collides with every other SVG there. Prefix every id and every reference to it:

```python
import re


def prefix_ids(svg: str, prefix: str) -> str:
    """Prefix ids and the url(#), href="#" references that point at them."""
    svg = re.sub(r'(\s)id="([^"]+)"', rf'\1id="{prefix}-\2"', svg)
    svg = re.sub(r"url\(#([^)]+)\)", rf"url(#{prefix}-\1)", svg)
    return re.sub(r'href="#([^"]+)"', rf'href="#{prefix}-\1"', svg)
```

- The `href` pattern also catches `xlink:href`. Check `begin="x.end"` references by hand; they need the same prefix.
- Wrap each prefixed icon in a `<symbol id="i-NAME" viewBox="...">` and place it with `<use href="#i-NAME">`; repeated icons then cost one copy.
- SVGO's `prefixIds` plugin does the same for exported files (it also prefixes class names by default).

## 4. Size budgets

| Item | Budget |
| --- | --- |
| one standalone file | aim under 50 KB, hard stop 100 KB unless the user accepts more (`validate_svg.py` SV013: error above 100 KB, warning above 50 KB; `--max-kb N` changes it; 200 KB for `--target web`) |
| embedded raster icon | 64 KB, at 2x its drawn size (SV020 warns above 64 KB) |
| embedded raster logo | 256 KB, at 2x its drawn size |
| embedded font | avoid; subset to the drawn glyphs if the font is the point |

Where the bytes go, largest first: embedded rasters (a certificate wall fell from 728 KB to 310 KB by embedding badges at 2x drawn size), embedded fonts (the readme-typing-svg card is 9,886 bytes with its font), duplicated geometry, then long decimals.

Cheap wins without a tool:
- One decimal for coordinates, three for `keyTimes`; format numbers with `:g` so `12.0` prints as `12`.
- `<symbol>` + `<use>` for repeated shapes, `<pattern>` for repeated textures.
- Font stacks and shared styles in one `<style>` class instead of repeated attributes.
- Drop invisible precision: strokes under 0.5 px and opacities under 0.02 are not seen.

## 5. Determinism

Generated files go into git, so the same input must produce the same bytes:
- No timestamps, no unseeded randomness (derive any jitter from the input), stable iteration order, fixed number formatting.
- Write UTF-8 with `newline="\n"` (a Windows run otherwise writes CRLF), and only when the bytes changed, so a quiet scheduled run makes no commit.
- On a failed data fetch keep the last good file; never render an empty card over it.
- CI check: run the generator twice and compare, or regenerate and `git diff --exit-code`.
- Never hand-edit a generated SVG; the next run overwrites it.
