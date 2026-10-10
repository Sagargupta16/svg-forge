# Kit primitives

A small copy-in TypeScript kit for React 19 and Motion (`motion/react`). Copy the kit folder of this skill into the app (for example `src/scenes/kit/`), keep the files together, and edit them like your own code; there is no package to install besides `react` and `motion`. It type-checks under `strict`, `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.

| File | Depends on |
| --- | --- |
| `tokens.ts` | react types |
| `timing.ts` | motion types |
| `routes.ts` | tokens, timing |
| `primitives.tsx` | tokens, timing, motion |
| `useNearViewport.ts` | motion |
| `useFreezeAnimations.ts` | react |
| `ExampleScene.tsx` | all of the above |

## tokens.ts: stage and palette

- `STAGE_W`, `STAGE_H`, `VIEWBOX`: the stage in units, 320 x 200 for 16:10. Change both for another slot ratio; everything else derives from them.
- `Pt`, `Box`: `[x, y]` and `[x, y, w, h]` in stage units.
- `pctX`, `pctY`, `pctAt`: stage units to percent of the stage box (for HTML positions and gradient centres).
- `layer`: `position: absolute; inset: 0`.
- `dotAt(at, size, color)`: style for a fixed px dot centred on a stage point.
- `alpha(hex, a)`, `mix(a, b, f)`: 8 digit hex with alpha; opaque blend of two hex colors.
- `createPalette({ tint, scheme, ok, warn, ink, mono })`: the whole palette from one tint. Returns `tint`, `ok`, `warn`, `ink`, `neutral`, `mono`, `base` (root background), `solid` (opaque panel fill) and the ladders `t` (tint) and `n` (neutral) with steps 3, 5, 10, 16, 25, 40, 55, 70, 88.
- `texture(kind, palette)`: back-layer pattern (`dots`, `grid`, `rails`, `columns`, `none`) and its cell size.

```ts
const palette = useMemo(() => createPalette({ tint, scheme: "dark" }), [tint]);
palette.t[55]; // tint at 55 percent, e.g. "#60a5fa8c"
palette.n[10]; // neutral at 10 percent, the hairline color
```

## timing.ts: one clock

- `PRESET`: default seconds for `micro`, `short`, `medium` (6), `long` (12), `ambient` (32).
- `ambient(distance, pxPerSecond = 40)`: duration of a drift or marquee from its speed.
- `Tracks`, `Keys`, `Loop`: animatable tracks; tracks plus `times` (and optional `ease`); keys plus `duration` (and optional `delay`).
- `clock(duration)`: binds a scene's cycle once; `beat(keys)` returns a `Loop`.
- `loopProps(loop)`: `{ initial, animate, transition }` to spread on any motion element. `initial` is frame 0; the transition repeats forever with one ease per segment.
- `perSegment(times, ease)`: the per-segment ease array on its own.
- `shown(on, off, ramp)`: opacity window. `windowTimes(on, off, rise, fall)` with `windowKeys(rest, peak)`: the same shape for any value.
- `firstFrame(tracks)`: the first value of every track.

```ts
const beat = clock(PRESET.medium);
const BUSY = beat(shown(0.21, 0.32));
const POP = beat({ times: windowTimes(0.6, 0.66), scale: windowKeys(1, 1.4), opacity: windowKeys(0, 1) });
```

## routes.ts: things in flight

- `line(a, b)`, `sCurve(a, b)`: one cubic segment; `sCurve` has horizontal tangents at both ports. `curveD(cubic)`: its path string.
- `route(...cubics)`: a chain with one arc-length parameter `s` from 0 to 1 over the whole length. Gives `d` for the SVG path, `ends` (fraction where each segment ends) and `at(s)`.
- `Stop`, `Stops`: `[cycle fraction, route fraction]`. Equal route fractions on consecutive stops hold.
- `ride(route, stops)`: transform and opacity keys for a packet. Fades in on the first stop, eases between stops along the curve, fades out after the last stop and slides home hidden.
- `comet(stops, len)`: `pathLength` and `pathOffset` keys for a trail of at most `len` that follows the head either way and collapses into it on holds. Draw it with `Trace` on the same route's `d`.
- `lit(stops, hold)`: the route lights up behind the packet and holds until `hold`.
- `passAt(a, b, s)`: when a move from stop `a` to stop `b` crosses route fraction `s`. Use it to time the effect a packet causes.

```ts
const RAIL = route(line([70, 100], [250, 100]));
const LEAVE: Stop = [0.04, 0];
const ARRIVE: Stop = [0.22, 1];
const CALL: Stops = [LEAVE, ARRIVE, [0.3, 1], [0.48, 0]];
const dot = beat(ride(RAIL, CALL));
const trail = beat(comet(CALL, 0.14));
const MISS_AT = passAt(LEAVE, ARRIVE, 0.5); // packet crosses the middle
```

## primitives.tsx: the parts

**Shell** is the root of every scene. It provides the palette and the frozen flag to everything inside, paints the base, the texture (masked from the focal point, optionally drifting) and one tint wash, and lays out the `Stage`. Root is `aria-hidden` and clipped.

```tsx
<Shell palette={palette} focus={[160, 100]} texture="grid" frozen={frozen} svg={<Board />}>
  <Packet loop={dot} />
  <Label at={[128, 58]}>Cache</Label>
</Shell>
```

**Stage** is the container-query box at the stage ratio, letterboxed (`fit="contain"`) or cropped (`fit="cover"`), holding an SVG with the stage viewBox (`svg` prop) and the HTML front layer (children). Use it alone when the host already paints its own background.

**Panel** (SVG): a rect with a 1 px hairline border. Defaults: fill `n[3]`, stroke `n[10]`, radius 6. Pass `fill={palette.solid}` when wires pass under it, `stroke="none"` for bars and chips, and a `loop` to fade it as one node (a lit state drawn over the resting panel).

**Wire** (SVG): static 1 px hairline, `non-scaling-stroke`, optional `dash`. Never animate it; animate a `Trace` or a `Packet` on the same `d` instead.

**Trace** (SVG): animated stroke for `pathLength` and `pathOffset` (comets, draws, lit routes). No vector-effect, so the normalised dash lands on the keyframes; width is in stage units and scales on purpose; butt caps so a zero-length dash paints nothing.

**Packet** (HTML): a fixed px head in a stage-sized wrapper, so `ride`'s percent translates are stage coordinates at any width. Color defaults to the tint.

**Pip** (HTML): status dot at a stage point; pulses with a `loop`, sits still without one. Use `palette.ok` and `palette.warn` only for status.

**Label** (HTML): mono uppercase micro label at a stage point, hanging to its right or `centered`. Offsets use the CSS `translate` property, so a Motion transform on the same element composes with it instead of replacing it.

**FadeLayer** (HTML): an overlay that fades on its own keys; everything inside costs one animated node.

**useScene()** returns `{ palette, frozen }` of the nearest `Shell`. **useLoop(loop)** returns loop props that honor `frozen` (frame 0 only, nothing started). Use it for custom motion elements inside a `Shell`:

```tsx
const Gauge = ({ loop }: Readonly<{ loop: Loop }>) => {
  const { palette } = useScene();
  const anim = useLoop(loop);
  return <motion.circle cx={160} cy={60} r={4} fill={palette.tint} {...anim} />;
};
```

## Hooks for the host

**useNearViewport(margin = 300)** returns `[ref, near]`; `near` is true while the element is within `margin` px of the viewport. Mount the scene only while it is true and paint a placeholder with `palette.base` otherwise.

**useFreezeAnimations(ref, frozen)** pauses every Web Animations API animation in the subtree at time 0 while `frozen` is true, and keeps sweeping on the next frames and on subtree mutations because Motion starts animations after commit and lazy scenes mount late. Kit primitives already stop through `Shell frozen`; this catches CSS keyframes and any motion element that does not use `useLoop`.

## ExampleScene.tsx

A read-through cache on one 6 s clock: call 1 misses at the cache (warn pip), reaches the database, which lights while it works, and the response fills the cache slot on its way back; call 2 stops at the cache (ok pip) and returns; the entry expires while the loop resets. 8 animated nodes (10 WAAPI animations: two packets with transform and opacity, six opacity tracks), 3 labels, every beat derived with `passAt`.

`SceneSlot` in the same file is the host pattern: fixed 16:10 box, near-viewport mount, placeholder in `palette.base`, `frozen` from the app's setting, `useFreezeAnimations` as backstop, scene keyed on the setting.

```tsx
<SceneSlot tint={card.accent} reduced={motionSetting === "reduced"} />
```

Measured in Chrome with Motion 14.1.0: the scene runs 10 WAAPI animations on one 6000 ms duration, the easing scan returns 0, packets and trails move between samples 700 ms apart, and the frozen scene runs 0 animations with no computed-style change over 800 ms.
