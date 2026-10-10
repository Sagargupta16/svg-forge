---
name: motion-scene
description: >-
  Designs and builds animated React and Motion (motion/react) scenes for web
  apps, such as project cover art, service card illustrations, hero art and
  architecture or mechanism diagrams that show what a thing actually does.
  Works in three modes, research (read the subject into a storyboard brief),
  build (implement it with a copy-in TypeScript kit) and verify (browser
  checks and gates). Use when the user asks for an "animated illustration",
  "cover scene", "hero animation", "diagram animation in React", "Motion
  animation for a card", an animated project or service card, a looping
  mechanism scene, or runs /motion-scene [research|build|verify]. Standalone
  .svg files go to animated-svg; reviews of existing art go to svg-audit.
argument-hint: "[research|build|verify] <subject>"
---

# motion-scene

A scene is a looping, decorative React component that shows a mechanism (input -> processing -> output) inside a fixed slot of a web app: the media area of a project card, the art column of a service card, a hero panel, a diagram in a docs page. The bar is accuracy. Someone who knows the subject should recognise its mechanism in one glance at card size. A generic "dashboard with bars" is a failure even when it looks good.

Delivery target is `scene` (a React + Motion component). Timing presets use the shared names `micro`, `short`, `medium` (default), `long` and `ambient`.

## Which skill

| Need | Skill |
| --- | --- |
| Animated component rendered inside a React app (card art, hero, diagram, illustration) | motion-scene |
| One self-contained `.svg` for a README, docs site or `<img>` (no script, SMIL and CSS only) | animated-svg |
| Review or fix an existing SVG file or scene component | svg-audit |

If the app is not React, or the art must also work as a plain image, use animated-svg. If the user only wants a quick hover or press effect on existing UI, that is a `micro` interaction, not a scene; apply the spring rules in [references/motion.md](references/motion.md) directly.

## Settle these first

Infer from the codebase; ask only what cannot be inferred.

- **Slot**: where it renders, its ratio, its smallest and largest rendered width (phone and desktop), and any overlay the host draws on it (bottom fade, badge, title).
- **Tint**: the one accent the host passes in (category color, brand accent). Everything else is neutral.
- **Scheme**: dark or light canvas.
- **Count**: how many instances can be on screen (a grid of 40 cards changes the budget and needs near-viewport mounting).
- **Motion setting**: does the app have its own motion control (an in-app Full/Reduced toggle, a settings flag)? Scenes follow it. Never add a reduced-motion gate to an app that has its own motion control. If the app has none, keep motion on and ask before adding one.

## Modes

`research` writes a brief, `build` implements a brief, `verify` proves it in the browser. A bare invocation infers the mode from the ask. Always research before building; never build from a README blurb alone.

### research

Read, in order: the README, the package manifest (`package.json`, `pyproject.toml`, `*.tf`, `*.csproj` ...), the entry point, the UI components or CLI command definitions, any screenshots or asset folder. Prefer code over README claims. For a service card with no repo, the truth is what is actually delivered under that heading; depict the deliverable, not the buzzword. For an architecture diagram, read the infrastructure source (IaC, compose files, service definitions), not a slide.

Write the brief before touching code:

```markdown
## Brief: <subject>
- What it does: one or two sentences, from the code.
- Mechanism: <input> -> <processing> -> <output>, in the subject's own nouns.
- Vocabulary: 6 to 10 terms that appear verbatim in the source (commands,
  files, tables, models, UI labels). Labels come only from this list.
- Visual identity: what the real UI, CLI or pipeline looks like.
- Current art: none | accurate | generic-but-fitting | partly-wrong | misleading,
  with what it gets right and wrong.
- Strategy: keep | retune-labels | new-variant | new-scene
  (new-scene only when the current art misrepresents the subject).
- Slot: ratio, smallest and largest width, overlays, tint, scheme, count,
  motion setting.
- Preset: medium (3 to 6 s loop) unless the story needs long (8 to 20 s).
- Storyboard, 3 to 6 beats on one clock, as cycle fractions:
  1. 0.04 to 0.22  <what moves, from where to where, which pip or label>
  2. ...
- Budget: <n> animated nodes, <m> labels (see composition budgets).
- Evidence: file and line for every claim above.
```

Each beat must be buildable with absolutely positioned SVG and HTML at the smallest slot width. If a beat only reads at hero size, cut it or move it to a `long` storyboard.

### build

1. **Copy the kit** into the app (for example `src/scenes/kit/`): [tokens.ts](assets/kit/tokens.ts), [timing.ts](assets/kit/timing.ts), [routes.ts](assets/kit/routes.ts), [primitives.tsx](assets/kit/primitives.tsx), [useNearViewport.ts](assets/kit/useNearViewport.ts), [useFreezeAnimations.ts](assets/kit/useFreezeAnimations.ts). It needs React 19 and `motion`. If the slot is not 16:10, change `STAGE_W` and `STAGE_H` in `tokens.ts` together. Read [references/primitives.md](references/primitives.md) for what each part does.
2. **Start from the storyboard**, not from another scene's shapes. Place parts in stage units (320 x 200 for 16:10). SVG geometry uses the stage viewBox; HTML packets, pips and labels sit at stage percentages with fixed px sizes. See [references/composition.md](references/composition.md).
3. **One clock.** `const beat = clock(PRESET.medium)` and every loop goes through `beat(...)`. Times are cycle fractions. Derive event times (`passAt`) instead of hand-tuning them. See [references/motion.md](references/motion.md).
4. **Compose from the primitives**: `Shell` (root, palette, texture, tint wash, stage), `Panel` and `Wire` in the SVG layer, `Trace` for animated strokes, `Packet` with `ride` and `comet` for data in flight, `Pip` for status, `Label` for the 3 or 4 words, `FadeLayer` to fade a group as one node. Custom motion elements inside a `Shell` take `useLoop(loop)` so they freeze with the rest.
5. **Variants, not forks.** Subjects that share a mechanism get one scene family with a `variant` prop, dispatched through a `Record` with a real fallback. A variant must change a moving element, not only label text.
6. **Mount through a host slot**: a fixed-ratio box, the scene lazy-loaded, mounted only near the viewport (`useNearViewport`), a placeholder painted with `palette.base` otherwise, `frozen` wired to the app's motion setting, `useFreezeAnimations` as the backstop, and the scene keyed on the setting. `SceneSlot` in [ExampleScene.tsx](assets/kit/ExampleScene.tsx) is the pattern.
7. **Keep it lint-clean by construction** (readonly props, no nested ternaries, no nested template literals, hoisted repeated literals, small sub-components). One default export per scene file; split past about 450 lines. See [references/gotchas.md](references/gotchas.md).
8. Run the app's own gates (lint, type-check, format, tests, build), then verify.

[ExampleScene.tsx](assets/kit/ExampleScene.tsx) is a complete 6 s read-through cache loop built only from the kit: 8 animated nodes, 3 labels, two packets on one route, derived miss, fill and hit beats.

Scene contract:

- Props `Readonly<{ tint: string; frozen?: boolean }>`, plus `variant?: string` only in a family that reads it.
- Root is `Shell`: absolute, inset 0, clipped, `aria-hidden="true"`. The host card's title and text carry the meaning.
- Default export, lazy-loaded by the host so scenes stay out of the entry chunk.

### verify

Run the app, open the page in a focused tab after a hard reload, and work through [references/verify.md](references/verify.md). The short version:

- Screenshot at the smallest and largest real slot widths; the mechanism reads at both.
- Animated node count within budget; running animations in view under about 70.
- Easing scan returns 0; every loop shares one duration.
- Two full cycles watched: no seam jump. Transforms sampled twice 700 ms apart differ.
- No horizontal overflow at 375 px; paint flashing shows the card body is not repainting.
- Root is `aria-hidden`; no decoration sits over text or controls.
- With the app's reduced setting on, an 800 ms computed-style diff shows 0 changes and the artwork is still visible.
- The app's gates pass. One scene family per commit.

Report each check with its measured value, not "looks fine".

## Hard rules

1. **Mechanism, not category.** Input -> processing -> output in the subject's own nouns. Changing label text does not make a scene accurate. [composition](references/composition.md)
2. **Labels**: at most 4 (2 on icon-size cards), uppercase mono, 7 to 9 px, 12 characters or fewer, no dashes, real vocabulary only, rendered as HTML so they keep their px size. No prose and no numbers that read as claims. [composition](references/composition.md)
3. **Palette is the tint plus neutrals.** Alpha ladders of one tint and one neutral; ok green only for live or success, warn amber only for warnings. No new hue, gradient text, glow halo or blur filter. [composition](references/composition.md)
4. **One stage at the slot ratio**: uniform viewBox, HTML at stage percentages with fixed px sizes, letterboxed by a container-query stage. Never stretch with `preserveAspectRatio="none"` unless the viewBox matches the slot exactly. [composition](references/composition.md)
5. **Budgets**: 12 or fewer animated nodes per cover, 8 or fewer per icon-size card, 3 to 6 beats, under about 70 running animations in view; mount loops only near the viewport. [composition](references/composition.md)
6. **Transform and opacity only** (plus SVG `pathLength` and `pathOffset` for stroke draws). Never animate width, height, top, left, filter or box-shadow. [motion](references/motion.md)
7. **One clock per scene.** One duration for every loop, events as cycle fractions; ambient backdrops may run slower on their own speed. [motion](references/motion.md)
8. **Per-segment easing whenever `times` is set**: `ease: perSegment(times)`. A single ease string drifts WAAPI tracks off the storyboard. [motion](references/motion.md)
9. **Seamless loops**: last keyframe equals the first, or the reset happens while the element is invisible. [motion](references/motion.md)
10. **Never put `pathLength` or `pathOffset` on a path with `vector-effect="non-scaling-stroke"`.** Static hairlines (`Wire`) and animated draws (`Trace`) are separate elements. [gotchas](references/gotchas.md)
11. **Decoration only**: root `aria-hidden`, nothing focusable inside, never over text or controls. [verify](references/verify.md)
12. **Follow the app's motion setting.** Freeze through `Shell frozen` and `useFreezeAnimations`; never add an OS-level gate to an app that has its own control. Motion stays visible by default. [gotchas](references/gotchas.md)
13. **Never start from `scale(0)`**; start at 0.9 to 0.97 (0.25 for icons). Exits run faster than entrances. [motion](references/motion.md)

## Kit files

| File | What it holds |
| --- | --- |
| [tokens.ts](assets/kit/tokens.ts) | Stage size, `pctX`/`pctY`, `createPalette` (tint, alpha ladders, base, solid), textures, `dotAt` |
| [timing.ts](assets/kit/timing.ts) | `PRESET`, `clock`, `perSegment`, `loopProps`, `shown`, `windowTimes`/`windowKeys`, `ambient` |
| [routes.ts](assets/kit/routes.ts) | `route`, `sCurve`, `line`, `ride`, `comet`, `lit`, `passAt` |
| [primitives.tsx](assets/kit/primitives.tsx) | `Shell`, `Stage`, `Panel`, `Wire`, `Trace`, `Packet`, `Pip`, `Label`, `FadeLayer`, `useLoop`, `useScene` |
| [useNearViewport.ts](assets/kit/useNearViewport.ts) | Mount a scene only within 300 px of the viewport |
| [useFreezeAnimations.ts](assets/kit/useFreezeAnimations.ts) | Pause every WAAPI animation in a subtree at time 0 |
| [ExampleScene.tsx](assets/kit/ExampleScene.tsx) | Complete 6 s mechanism loop plus the `SceneSlot` host pattern |

The kit type-checks under `strict`, `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` with React 19 and Motion 14.

## References

- [references/composition.md](references/composition.md): mechanism over category, labels, palette, depth layers, stage units and responsive layout, budgets, variants.
- [references/motion.md](references/motion.md): presets mapped to scene use, one clock, cycle fractions, per-segment easing and the WAAPI drift, seamless loops, stagger, springs vs tweens, enter and exit.
- [references/gotchas.md](references/gotchas.md): every known failure as symptom, cause, fix.
- [references/primitives.md](references/primitives.md): each kit part, when to use it, short snippets.
- [references/verify.md](references/verify.md): screenshot sizes, budgets, scan snippets, seam check, paint flashing, accessibility, reduced mode, gates.
