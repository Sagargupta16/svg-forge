# Gotchas

Each entry: what you see, why, and the fix. The kit already applies every fix; these matter when writing custom parts or reviewing someone else's scene.

## 1. Line draw stops short or renders dashed

- **Symptom**: a `pathLength` 0 to 1 draw stops about a third of the way, flickers, or shows as dashes in a scaled SVG.
- **Cause**: `vector-effect="non-scaling-stroke"` on the same path. Chrome sizes the normalised dash in user units but strokes the path in screen units, so the dash and the path disagree as soon as the SVG scales.
- **Fix**: keep two kinds of path. Static hairlines that must stay 1 px use `non-scaling-stroke` and never animate their stroke (`Wire`). Animated draws use plain strokes in a uniform viewBox (`Trace`, no vector-effect).

## 2. Opacity drifts away from position

- **Symptom**: a dot fades before it arrives, or holds look shorter than the storyboard says; worse on long holds.
- **Cause**: `times` with a single ease string. Motion sends opacity (and transform strings) to WAAPI, which applies the string over the whole iteration, while x, y and scale ease per segment on the frameloop. Full measurement in `motion.md`.
- **Fix**: `ease: perSegment(times)` on every keyframe loop. Verify with the easing scan after a hard reload; hot module reload keeps the old transition on mounted elements, so a fixed file can still scan dirty until you reload.

## 3. Circles become ovals, text squashes

- **Symptom**: round pips are ellipses, SVG text is stretched, stroke widths differ by direction.
- **Cause**: `preserveAspectRatio="none"` on an SVG whose viewBox ratio differs from the slot's. It is only safe when the two ratios match exactly, and slots that letterbox (a taller spotlight card, a resized hero) break that.
- **Fix**: one stage at the viewBox ratio inside a container-query box (`Stage`, `min(100cqw, 160cqh)` for 16:10), uniform scaling, and dots and labels as HTML with px sizes. Grid-based art (game boards) uses `xMidYMid meet`.

## 4. Labels unreadable at small sizes

- **Symptom**: on a phone the labels are 5 px smudges; on an icon-size card they vanish.
- **Cause**: label size authored for the desktop render, or labels drawn as SVG text that scales with the stage.
- **Fix**: HTML labels at 7 to 9 px (cover) or 5 to 7 px in source on icon-size canvases that the host scales up (5 to 5.5 px in an 80 px canvas that a phone layout scales 1.2x reads at about 6 px). Fewer labels at small sizes, and motion that carries the meaning without them.

## 5. Reduced mode still blinks

- **Symptom**: with the app's reduced setting on, transforms stop but dots keep blinking in place; toggling the setting at runtime changes nothing until reload.
- **Cause**: Motion's `reducedMotion` only makes positional values instant (width, height, top, left, x, y, scale, rotate). Opacity and transform strings keep running on WAAPI, and `pathLength` keeps running on the frameloop. `MotionConfig reducedMotion` is also read once at mount.
- **Fix**: pass the setting as `Shell frozen` (kit primitives paint frame 0 and start nothing), keep `useFreezeAnimations(ref, reduced)` on the host to pause any other WAAPI animation at time 0, and key the scene on the setting so a change remounts it. Anything whose stroke animates on the frameloop starts at opacity 0, so the frozen frame hides it (`ride`, `comet` and `lit` do). Frozen still shows the artwork; never hide it.

## 6. A grid of cards makes the page hot

- **Symptom**: scrolling a page of 30 or 40 animated cards stutters, fans spin, battery drains.
- **Cause**: every scene loops whether it is on screen or not.
- **Fix**: mount the scene only within about 300 px of the viewport (`useNearViewport`) and paint a placeholder with the same base gradient otherwise (`palette.base`), so the swap is invisible. That keeps a handful of scenes alive instead of all of them. Keep running animations in view under about 70.

## 7. The texture fade slides with the drift

- **Symptom**: a drifting dot or grid lattice drags its radial fade across the slot, so the bright spot wanders.
- **Cause**: the mask is on the same element that drifts.
- **Fix**: put the mask on a static parent and drift a child larger than the slot by one cell (`Shell drift` does this).

## 8. Measurements look wrong or frozen

- **Symptom**: sampled values repeat, loops look stuck, frame timings are huge.
- **Cause**: background or unfocused tabs throttle rendering to about one frame per 300 ms.
- **Fix**: measure only in a focused, visible tab; bring the page to the front before sampling and compare against `requestAnimationFrame` timestamps.

## 9. Packets stutter under load

- **Symptom**: motion is smooth on an idle page and janky while the page scrolls or hydrates.
- **Cause**: Motion's `x` and `y` shorthands run on the JS frameloop (main thread). Only `opacity`, `transform`, `filter`, `clipPath` and `backgroundColor` are handed to the browser's animation engine.
- **Fix**: animate continuous travel as full `transform` strings (`ride` emits `translate(x%, y%)` keyframes). Keep `x`/`y`/`scale` for short pops.

## 10. A track silently leaves WAAPI

- **Symptom**: the easing scan or `useFreezeAnimations` misses an animation you can see moving.
- **Cause**: `repeatDelay`, `repeatType: "mirror"`, an `onUpdate` callback, `type: "inertia"`, a spring with `damping: 0`, or a `transformTemplate` (for `transform`) each disable Motion's WAAPI path for that value, so it runs on the frameloop and never appears in `getAnimations()`.
- **Fix**: write holds into `times` instead of `repeatDelay`, write the return trip into the keyframes instead of `mirror`, and keep loops as plain tweens.

## 11. Animation never starts, console shows an offsets error

- **Symptom**: one element sits still; the console shows a TypeError about keyframe offsets.
- **Cause**: hand-computed `times` below 0, above 1 or out of order (a fade that starts `FADE` before a stop at 0.01).
- **Fix**: clamp derived times into 0 to 1 (`ride` and `comet` clamp their fades) and keep each list non-decreasing with one value per keyframe.

## 12. A dot appears at the start of an empty trail

- **Symptom**: a faint dot sits at the head of a trail whose length is 0.
- **Cause**: round or square stroke caps paint even on a zero-length dash.
- **Fix**: butt caps on animated strokes (`Trace` default), or opacity 0 whenever the length is 0.

## 13. Hover lift stops working after a tap

- **Symptom**: on touch devices a card's resting offset snaps away after the first tap.
- **Cause**: `whileTap` leaves `transform: none` inline on the element when it finishes.
- **Fix**: keep resting transforms on an inner element; let the tapped element own only the interaction transform.

## 14. Flash when the scene mounts

- **Symptom**: a dark or white flash as a lazy scene replaces its placeholder.
- **Cause**: the placeholder paints a different background than the scene's base.
- **Fix**: paint the placeholder and the lazy-load fallback with `palette.base`, and give the slot a fixed aspect ratio so nothing shifts.

## 15. Lint flags the scene

Sonar-style rules that scene code trips most, as code-quality guidance whether or not the project runs Sonar:

| Rule | Write instead |
| --- | --- |
| S6759 props should be read-only | `Readonly<Props>` on every component |
| S7755 prefer `.at(-1)` | `arr.at(-1)`, not `arr[arr.length - 1]` |
| S4624 no nested template literals | hoist the inner literal to a const or helper |
| S3358 no nested ternaries | a `Record` lookup or an `if / else if` chain |
| S6767 unused prop types | declare `variant` only in a family that reads it |
| S1192 duplicated literals | hoist repeated strings (`"none"`, colors) to constants |
| S3776 cognitive complexity over 15 | split sub-panels into small components in the same file |

## 16. A label jumps off its point when it moves

- **Symptom**: a centred HTML label snaps left or up the moment its loop starts.
- **Cause**: the label is centred with `transform: translate(-50%, -50%)` and the loop animates `x` or `y`, which Motion writes into the same `transform`.
- **Fix**: fade the label and move its parent, or centre with the CSS `translate` property as the kit's `Label` does, so `transform` stays free for the loop.

## 17. The frozen frame is half built

- **Symptom**: with the app's reduced setting on, a scene shows an empty stage, or a packet stuck mid-wire.
- **Cause**: the loop builds up from nothing and frame 0 is its empty state.
- **Fix**: open on the finished state and clear in the first 4 to 8 percent (`motion.md` section 6), or start every element that builds up hidden so frame 0 is a clean rest pose.
