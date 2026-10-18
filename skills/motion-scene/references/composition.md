# Composition

What goes on the stage, where, and in which colors. Motion rules live in `motion.md`; the parts named here are in the kit (`primitives.md`).

## 1. Mechanism over category

- Show what the subject does, as input -> processing -> output, in its own nouns: command names, file names, table names, model names, UI labels. Read the code, not the README.
- The test: someone who knows the subject recognises it in one glance at the smallest slot width. A generic "dashboard with bars", "cloud with arrows" or "brain with sparkles" fails even when it looks good.
- Labels are not accuracy. One generic scene reused for six unrelated subjects with only the chip text changed is still wrong for five of them.
- Geometry carries identity. If the scene needs a label to be recognised, the drawing has failed; fix the drawing before the words.
- Depict the subject, not its technology. A tax tool whose value is the computation shows the computation, not a protocol hub diagram because it happens to speak that protocol.
- For a service or offering with no repo, depict the deliverable (a module library with its tests, a blue/green cutover, a pipeline with a drift alarm), not the buzzword.
- A deployed app gets a scene, not a screenshot. The scene echoes the real UI at the mechanism's moment: the panel layout in slot percent, rows as bars, the one control or state that matters, and none of the rest of the chrome.
- Good mechanisms have a visible cause and effect inside one loop: a request is denied at a layer, a cache slot fills on the way back, a canary takes one request in two, a job retries once and lands.

## 2. Labels

| Slot | Max labels | Size | Length |
| --- | --- | --- | --- |
| Cover or card art (about 300 to 400 px wide) | 4 | 7 to 9 px | 12 chars or fewer |
| Icon-size card (an 80 px source canvas the host scales 1.5x on phones, 1.8x on desktop) | 2 | 6 px in source, so 9 to 10.8 px rendered, never smaller | 10 chars or fewer |

- Uppercase monospace, letter-spacing about 0.08em, no dashes of any kind.
- Words come only from the brief's vocabulary list (verbatim terms from the source).
- Labels are HTML (`Label`), not SVG `<text>`. HTML keeps its px size at every slot width; SVG text scales with the stage, turning to mush at 165 px and shouting at hero size.
- No prose and no numbers that read as claims ("99.9%", "10x", fake metrics). The host card's title and description carry meaning; the scene is decoration.
- At small scales labels become texture. The motion must still carry the mechanism without them.
- Everything that would be text but is not one of the labels is a bar: a rounded rect 2.5 to 4 px tall at `n[16]` to `n[40]`, uneven lengths so a file reads as a file. Never real words as decoration.

## 3. Palette: one tint plus neutrals

Build everything from `createPalette({ tint, scheme })`:

| Token | Use |
| --- | --- |
| `p.base` | Root background: the ink with a faint lift of tint at the top left |
| `t[10]` | The single radial tint wash at the focal point (fades out by 60%) |
| `p.tint`, `t[55]` | Packets, active strokes, comet trails |
| `t[16]`, `t[25]` | Lit panel fill, highlighted chip |
| `n[3]` | Panel fill |
| `n[5]` | Texture lines, empty slots |
| `n[10]` | Panel borders, static wires |
| `n[16]`, `n[25]` | Bars, secondary marks |
| `n[55]` | Labels |
| `n[70]`, `n[88]` | Lit label, emphasised mark |
| `p.solid` | Opaque panel fill, for panels that wires pass under |
| `p.ok` | Live, success, cache hit, check passed. Status only |
| `p.warn` | Warning, miss, denied, drift. Status only |

- The tint comes from the host (the card's accent, the brand color). Pass a 6 digit hex; ladders are 8 digit hex, valid in SVG attributes and CSS.
- Never add a hue because the real product uses it. A grid of 40 cards must read as one palette.
- One highlight at a time: at rest one bright mark (`t[55]` or `n[88]`) says where to start, and when a beat chooses a part the bright moves to it and the rest mark gives it up.
- Never: gradient text, glow halos (box-shadow or drop-shadow), blur filters, a rainbow of per-item colors.
- `scheme: "light"` swaps the neutral to a dark ink on a light canvas. Check that `n[55]` labels still read on it.

## 4. Depth layers

1. **Back**: base gradient, one texture (`dots`, `grid`, `rails`, `columns`) at 4 to 7 percent neutral, one tint wash. Static, or an ambient drift under 1 px per second. The texture fades out from the focal point through a mask on a static parent.
2. **Middle**: SVG panels (1 px hairline border `n[10]`, radius 4 to 8, fill `n[3]`), static wires, animated strokes. Draw order is the depth: wires first, opaque panels over them so wires end cleanly at panel edges, traces last.
3. **Front**: HTML packets, status pips and labels. Things that move between parts live here so they ride over panels.

Decoration never sits over the host's text, buttons or links.

## 5. Stage units and responsive layout

- One stage at the slot's own ratio: 320 x 200 units for 16:10, about 1.1 px per unit on a 350 px card. For another ratio change `STAGE_W` and `STAGE_H` together.
- SVG geometry is in stage units under a uniform viewBox, so circles stay round and `pathLength` draws land exactly.
- HTML parts sit at stage percentages (`pctX`, `pctY`, `dotAt`) with fixed px sizes: packet heads 4 to 6 px, pips 4 to 6 px, labels 8 px. They stay legible on a 165 px phone card and do not balloon on a hero.
- `Stage` is a container-query box: `min(100cqw, 160cqh)` by `min(100cqh, 62.5cqw)` for 16:10, centred. `fit="contain"` letterboxes inside any slot (the back layer still fills it); `fit="cover"` fills and crops, for heroes of arbitrary ratio. Keep the mechanism inside the central safe area when using cover.
- Design for the smallest render first, then check the largest.
- Keep a margin where the host draws overlays. A bottom fade that starts at 72 percent of the slot height means content stays above about y 170 of 200; corner badges need their corner clear.
- Position with stage coordinates you can name (`RAIL_Y`, `CACHE_X`) and derive the rest, so a layout change is one edit.
- Write the beat table as a comment at the top of the scene file (what moves, when, as cycle fractions, plus the node and label counts), so the storyboard ships with the code and a later edit moves a window instead of guessing.

## 6. Element budgets

| Slot | Animated nodes | Labels | Beats | Preset |
| --- | --- | --- | --- | --- |
| Cover or card art | 12 or fewer | 4 | 3 to 6 | medium |
| Icon-size card | 8 or fewer | 2 | 2 to 4 | medium |
| Page total | under about 70 running animations in view | | | |

- An animated node is one element with a loop. A `FadeLayer` counts once for its whole group.
- Browser animation counts are higher than node counts: a `Packet` riding a route is 2 WAAPI animations (transform and opacity), a `Trace` is 1 WAAPI (opacity) plus frameloop tracks. The kit's example scene is 8 nodes and 10 WAAPI animations.
- A grid of many cards needs near-viewport mounting; budget per card assumes only a handful are mounted.
- Keep scene files under about 450 lines; past that, split sub-panels into small components or split the family.

## 7. Variants, not forks

- Subjects that share a mechanism (several games on one engine, several servers on one protocol) get one scene family with a `variant` prop.
- Dispatch through `Record<string, Component>` with a real fallback, never a nested ternary:

```tsx
const VARIANTS: Record<string, ComponentType<SceneProps>> = { memory: MemoryVariant, compare: CompareVariant };
export default function ServerScene({ variant, ...props }: Readonly<SceneProps & { variant?: string }>) {
  const Variant = VARIANTS[variant ?? ""] ?? MemoryVariant;
  return <Variant {...props} />;
}
```

- A variant must change at least one moving element. If two variants differ only in labels, they do not share a mechanism and one needs its own scene.
- Declare `variant` in the props only where it is read.
