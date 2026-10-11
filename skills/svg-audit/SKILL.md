---
name: svg-audit
description: >-
  Audits an existing SVG file or animated React scene and returns ranked
  findings with fixes: render-target safety (GitHub README image proxy,
  browsers), accessibility, motion quality, file weight and code hygiene.
  Runs the bundled validator, then reviews what a linter cannot see. Use
  when the user says "audit this SVG", "why doesn't my SVG animate on
  GitHub", "check this README card", "is this SVG accessible", "review my
  animation", "shrink this SVG", or runs /svg-audit [file]. Reports first;
  only edits files when the user asks for the fixes.
argument-hint: "<file.svg | Scene.tsx> [--fix]"
---

# svg-audit

Find what is wrong with an SVG or an animated scene, rank it by how much it hurts, and say exactly how to fix each item. Default mode is read-only: print the report and stop. Apply fixes only when the user asks ("fix it", "--fix", "apply").

## 1. Identify the artifact and its target

| Artifact | Target | Primary references |
| --- | --- | --- |
| `.svg` shown through `<img>` in a README, docs site or email | standalone | [github-readme](../animated-svg/references/github-readme.md), [smil-and-css](../animated-svg/references/smil-and-css.md) |
| `.svg` inlined in a web page | web | [smil-and-css](../animated-svg/references/smil-and-css.md), [accessibility](../animated-svg/references/accessibility.md) |
| React component animated with Motion | scene | [motion](../motion-scene/references/motion.md), [verify](../motion-scene/references/verify.md) |

Ask only if the target cannot be inferred from where the file lives or how it is referenced (grep the repo for its filename).

## 2. Run the validator (SVG files)

```bash
python skills/animated-svg/scripts/validate_svg.py path/to/file.svg --target standalone --strict-contrast --json
```

Use `--target web` for inline page SVGs. For one half of a `<picture>` pair add `--theme dark` or `--theme light`; otherwise text with no background of its own is measured on both GitHub pages. Every error is a finding. Warnings become findings when they matter for the target. Quote rule ids (SV0xx) so the user can look them up; SV021-SV023 are WCAG contrast (text 4.5:1, large text and solid shapes 3:1), with each measurement under `stats.contrast`.

Then render the timeline so motion findings rest on frames, not guesses:

```bash
python skills/animated-svg/scripts/frames.py path/to/file.svg --theme both
```

Read the PNG contact sheet it writes: entrances, overlaps, labels that are hidden at rest, and whether the seam frame matches t=0. Exit 3 means no browser was found; say so in the report instead of guessing.

For a scene component, there is no validator: read the component and its helpers instead, and apply the checks in section 3.

## 3. Review what the validator cannot see

Work through each lens and record findings with a file and line.

**Render-target safety**
- Standalone: anything that needs network, script, or an HTML context fails silently on GitHub. External fonts fall back to system fonts, so check text still fits.
- Dark and light: text needs 4.5:1 and marks 3:1 on both GitHub themes (the validator measures this), or the file must ship as a `<picture>` pair. In-SVG `prefers-color-scheme` does not follow GitHub's theme and fails on WebKit. For a fix, regenerate with forge.py `--theme both` or a preset; it tunes every color to pass.
- Browser quirks: SMIL path morphs are the only morphs Safari plays; `calcMode` misspelled (`calcmod`) silently drops `keySplines`; `pathLength` together with `vector-effect="non-scaling-stroke"` stops line draws short in Chrome.

**Motion quality**
- One clock: beats in a loop should share one duration so they never drift apart.
- Seamless loop: the last keyframe equals the first, or the restart happens while the element is invisible.
- Easing: multi-keyframe animations need per-segment easing (`keySplines` per segment, or an `ease` array in Motion when `times` is set).
- Budget: count animated elements; more than about 12 in one scene, or 40 in one file, reads as noise and costs CPU.
- Only `transform` and `opacity` (plus stroke dash properties for line draws) should animate in scenes.

**Accessibility**
- Meaningful graphic: `role="img"` plus `<title>` (and `<desc>` when it carries information) referenced by `aria-labelledby`, or `alt` text on the `<img>`.
- Decorative graphic: `aria-hidden="true"` (inline) or empty `alt` (image).
- Auto-playing motion longer than 5 s has no pause control inside an image: note it, do not block on it.

**Weight and hygiene**
- Size against the budget for the target (standalone: aim under 50 KB, hard stop 100 KB unless the user accepts more). `python skills/animated-svg/scripts/optimize_svg.py FILE --check` reports what an animation-safe minify would save without writing anything.
- Embedded rasters at more than twice their drawn size, unused `<defs>`, duplicated paths that could be `<use>`.
- Ids prefixed and unique when the file inlines icons or may be inlined into a page.
- Deterministic output if the file is generated: same input, same bytes.

## 4. Report

Print a table ranked by severity, then a short verdict.

```
| # | severity | where | finding | fix |
| 1 | error    | card.svg:12 | <image href="https://..."> is blocked by GitHub's image proxy | inline it as a data URI under 64 KB, or drop it |
| 2 | warn     | card.svg:40 | 6 s loop with beats on 4 s and 6 s clocks drifts | put every beat on the 6 s clock |
verdict: renders on GitHub after fix 1; 2 is polish.
```

Severity: `error` (does not render or is unsafe), `warn` (renders but looks wrong somewhere or hurts access), `polish` (quality).

## 5. Fix mode (only when asked)

- Apply fixes in severity order, one finding at a time, keeping unrelated markup byte-identical.
- Re-run the validator after each change; the report's errors must reach zero.
- For generated files, fix the generator or its input, not the output.
- Show the diff and the new validator result.
