# Motion

How things move in a scene and in the host chrome around it. Examples use the kit helpers from `timing.ts` and `routes.ts`.

## 1. Transform and opacity only

- Animate `x`, `y`, `scale`, `rotate`, full `transform` strings and `opacity`. For SVG stroke draws, `pathLength` and `pathOffset`.
- Never animate `width`, `height`, `top`, `left`, `padding`, `filter`, `box-shadow` or `backdrop-filter`. They relayout or repaint every frame, and 40 cards turn the page into a fan heater.
- No permanent `will-change`; the browser promotes on demand.
- For HTML parts that travel continuously, prefer `transform` strings (`ride` emits them): Motion hands them to the browser's animation engine, while `x` and `y` shorthands run on the main thread.

## 2. Timing presets in scenes

| Preset | Range | Scene use | Kit |
| --- | --- | --- | --- |
| `micro` | 120 to 300 ms, one-shot | Hover, press and toggle feedback in the host card; never inside a loop | spring, or `PRESET.micro` tween |
| `short` | 0.4 to 1.2 s one-shot, stagger 60 to 120 ms, total under about 1.5 s | Entrance when a diagram first scrolls into view; a hero reveal | `whileInView` with `once`, `PRESET.short` |
| `medium` | 3 to 6 s seamless loop (default) | Mechanism scenes: cover art, card art, packets on a path, pulses | `clock(PRESET.medium)` |
| `long` | 8 to 20 s storyboard of 3 to 6 beats on one clock | Multi-step architecture diagrams, hero storyboards | `clock(PRESET.long)` |
| `ambient` | 20 to 60 s, defined by speed | Texture drift, slow glows, marquees | `ambient(distance, pxPerSecond)` |

- Ambient speed: marquees and rails about 40 px per second; backdrop lattice drift under 1 px per second (the kit's `Shell drift` moves one cell in about 30 s).
- Glows and backdrops may run on their own slow cycle (26 to 40 s). Everything that tells the story runs on the scene clock.

## 3. One clock per scene

```ts
const beat = clock(PRESET.medium); // 6 s
const BUSY = beat(shown(0.21, 0.32));
const MISS = beat(pop(MISS_AT));
```

- Every storyboard loop uses the same duration. A 4 s loop beside a 6 s loop lines up only every 12 s and the story falls apart between.
- Times are fractions of the cycle (0 to 1), so the whole scene can be retimed by changing one number.
- Derive event times instead of hand-tuning: `passAt(stopA, stopB, s)` returns when a packet moving from stop A to stop B crosses route fraction `s`, so the pip, the fill or the denial lands exactly when the packet gets there.
- `delay` only offsets the first iteration; with one shared duration the offset holds forever, so `delay: i * 0.3` (0.3 to 0.9 s) is a valid stagger for identical loops. For anything in the storyboard, bake the offset into `times`.

## 4. Cycle fractions and opacity windows

- `shown(on, off, ramp)` fades in at `on`, holds, and is gone by `off`: six keys `[0, on, on+ramp, off-ramp, off, 1]`.
- `windowTimes(on, off, rise, fall)` with `windowKeys(rest, peak)` does the same for any value (scale, a lit opacity of 0.6, a y offset).
- Every track in a loop has exactly as many values as `times`; `times` starts at 0, ends at 1 and never decreases.
- Generate keyframes from an event list rather than hand-writing long arrays:

```ts
const trips = [0.1, 0.35, 0.6].map((at) => ({ at, side: at < 0.5 ? -1 : 1 }));
const times = [0];
const y = [0];
for (const { at, side } of trips) {
  times.push(at, at + 0.1, at + 0.2); // leave, peak, back
  y.push(0, side * 24, 0);
}
times.push(1);
y.push(0);
```

## 5. Per-segment easing whenever `times` is set

Motion runs `opacity`, `transform` strings, `filter`, `clipPath` and `backgroundColor` through the Web Animations API (WAAPI) on HTML and SVG elements, and runs `x`, `y`, `scale`, `rotate`, `pathLength` and `pathOffset` on its own JS frameloop. With `times` and a single ease string, the frameloop eases each segment, but WAAPI gets the string as the effect easing over the whole iteration with linear keyframes. Opacity then drifts away from position and hold segments shrink.

Measured on Motion 14.1.0 with `times: [0, 0.2, 0.8, 1]` and `ease: "easeInOut"`: the WAAPI effect easing read `ease-in-out` with linear keyframes, and at cycle 0.78 (inside the hold, `x` still at its peak) opacity had already fallen to 0.5. With `ease: times.slice(1).map(() => "easeInOut")` the effect easing read `linear`, each keyframe `ease-in-out`, and opacity stayed 1 through the hold.

- Fix: always pass an ease array with one entry per segment. `loopProps` and `clock` do it (`perSegment(times, ease)`).
- Detect: in a focused tab after a hard reload (hot reload keeps old transitions), this must return 0:

```js
document.getAnimations().filter((a) => a.effect.getKeyframes().length > 2 && a.effect.getTiming().easing !== "linear").length
```

## 6. Seamless loops

- Every track's last keyframe equals its first, or the reset happens while the element is invisible.
- Packets: fade in on the first stop, travel and hold, fade out just after the last stop, slide home while hidden, fade back in next cycle. `ride` and `comet` emit exactly this.
- Linear sweeps move exactly one period: a texture drifts one cell, a marquee of two copies translates by -50 percent.
- Watch two full cycles; the seam is where jumps hide.

## 7. Stagger

- Loops: same clock, different phase (offsets inside `times`, or a constant `delay` for identical loops).
- Entrances: 60 to 120 ms per item with a short lead, capped so a grid fills fast (`Math.min(index * 0.05, 0.3)` s).
- Never stagger beats of one storyboard with separate durations.

## 8. Springs vs tweens

- Pointer causes, springs answer: card lift `y` -2 to -4 px on a spring around stiffness 380, damping 26; tap `scale: 0.97`; an icon pop around 420 / 16. Focus-visible gets the same state as hover.
- Time and scroll cause, tweens answer: every loop, reveal and fade.
- Gate hover effects to hover-capable pointers (`@media (hover: hover) and (pointer: fine)`); touch gets tap feedback only.
- Put hover transforms on a wrapper, not on the looping element, so the two never fight over `transform`.

## 9. Enter and exit

- Exits run faster than entrances (enter about 0.4 s, exit about 0.2 to 0.25 s); ease out on enter, ease in on exit.
- Never start from `scale(0)`: it pops and reads as a glitch. Start at 0.9 to 0.97 with opacity 0 (0.25 for small icons).
- Never animate decoration over text that is being read.

## 10. Motion setting

- Motion stays visible by default. Subtle to the point of invisible is a failure.
- Follow the app's own control. Pass it to the scene as `frozen` (kit primitives then paint frame 0 and start nothing) and keep `useFreezeAnimations` on the host as the backstop. Never add an OS-level reduced-motion gate to an app that has its own motion control.
- If the app has no control and the user wants the OS preference respected, map Motion's `useReducedMotion()` to `frozen` in the host; that is an opt-in, not a default.
