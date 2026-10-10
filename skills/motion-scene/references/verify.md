# Verify

A scene is done when it has been seen running at its real sizes and the numbers below were measured, not assumed. Run the app's dev server, open the page that renders the scene, hard reload (hot reload keeps old transitions on mounted elements), and keep the tab focused and visible: background tabs throttle to about one frame per 300 ms and every timing sample lies.

Paste the snippets into the DevTools console (it accepts top-level `await`), or run them through a browser automation tool. Define the slot selector first, for example `const SCENE = "[data-scene]";`.

## 1. Screenshots at real sizes

| Slot | Desktop | Phone |
| --- | --- | --- |
| Cover or card art | the card's real width (often 340 to 370 px) | a 375 px viewport (scene often about 165 px wide) |
| Icon-size card | as rendered (for example 144 px) | as rendered (for example 96 px) |
| Hero | 1280 px viewport | 375 px viewport |

The mechanism must read at both sizes. Labels may turn into texture on the phone; the motion must still tell the story. Take one screenshot per beat if the storyboard has distinct states, and look at them: numbers catch regressions, eyes catch ugliness.

## 2. Budgets

Count animated nodes in the scene file (every element with a loop; a `FadeLayer` counts once) against the budget in `composition.md`. Then measure the page:

```js
const el = document.querySelector(SCENE);
({
  scene: el.getAnimations({ subtree: true }).length,
  runningInView: document.getAnimations().filter((a) => a.playState === "running").length,
});
```

Keep running animations in view under about 70. `getAnimations()` only sees WAAPI tracks (opacity, transform strings); frameloop tracks (`x`, `y`, `scale`, `pathLength`) do not appear, so the node count from the source is the real budget.

## 3. Easing scan and one clock

```js
const anims = document.querySelector(SCENE).getAnimations({ subtree: true });
({
  badEasing: anims.filter((a) => a.effect.getKeyframes().length > 2 && a.effect.getTiming().easing !== "linear").length,
  durations: [...new Set(anims.map((a) => a.effect.getTiming().duration))],
});
```

`badEasing` must be 0. `durations` should hold one value (the scene clock), plus at most one slow ambient duration for a drifting backdrop.

## 4. It really moves

```js
const nodes = [...document.querySelector(SCENE).querySelectorAll("*")];
const read = () => nodes.map((n) => getComputedStyle(n).transform + getComputedStyle(n).opacity + (n.getAttribute("stroke-dasharray") ?? ""));
const a = read();
await new Promise((r) => setTimeout(r, 700));
const b = read();
a.filter((v, i) => v !== b[i]).length; // greater than 0 while running
```

## 5. Seam

Watch two full cycles at normal speed, then step through the wrap for WAAPI tracks:

```js
const anims = document.querySelector(SCENE).getAnimations({ subtree: true });
const at = (t) => {
  for (const a of anims) {
    a.pause();
    a.currentTime = t;
  }
  return anims.map((a) => getComputedStyle(a.effect.target).opacity + getComputedStyle(a.effect.target).transform);
};
const d = anims[0].effect.getTiming().duration;
const end = at(d - 1);
const start = at(0);
anims.forEach((a) => a.play());
end.filter((v, i) => v !== start[i]).length; // 0 for a seamless loop
```

Frameloop tracks are not in that list; watch the wrap by eye in a screen recording or slow the clock temporarily (`clock(PRESET.medium * 4)`).

## 6. Paint and overflow

- DevTools, Rendering, Paint flashing: only the scene's moving parts flash; the card body, text and siblings do not repaint.
- At a 375 px viewport, `document.documentElement.scrollWidth - innerWidth` is 0 or less.
- Nothing inside the scene exceeds its slot; `overflow: hidden` on the root should never be doing real work.

## 7. Accessibility

- The scene root is `aria-hidden="true"` and contains nothing focusable (`el.querySelectorAll("a,button,input,[tabindex]").length === 0`).
- The host card's title and text carry the meaning; no information exists only in the animation.
- Decoration never covers text or controls:

```js
const art = document.querySelector(SCENE).getBoundingClientRect();
const hit = (a, b) => !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
[...document.querySelectorAll("h1,h2,h3,p,a,button")]
  .filter((e) => !e.closest(SCENE) && hit(art, e.getBoundingClientRect())).length; // 0
```

## 8. Reduced mode

Turn on the app's own reduced setting (its toggle or settings flag; not the OS preference), then:

```js
const el = document.querySelector(SCENE);
const snap = () => [...el.querySelectorAll("*")].map((n) => getComputedStyle(n).transform + getComputedStyle(n).opacity + (n.getAttribute("stroke-dasharray") ?? ""));
const before = snap();
await new Promise((r) => setTimeout(r, 800));
const after = snap();
({
  changed: before.filter((v, i) => v !== after[i]).length,
  running: el.getAnimations({ subtree: true }).filter((x) => x.playState === "running").length,
});
```

Both must be 0, and the artwork must still be visible (panels, wires, labels present in a screenshot). Turn the setting off again and confirm the scene restarts without a reload.

## 9. Gates

Run the app's own gates: lint, type-check, format check, tests, build, and any data or registry validation the project has. Commit one scene family per commit so a regression is easy to bisect.

## Report

One line per check with its measured value (fill in the angle brackets; never write "looks fine"):

```
screenshots   <desktop> px and <phone> px: mechanism reads at both (attached)
budget        <n> nodes of <cap>, <w> WAAPI in scene, <r> running in view
easing        badEasing 0, durations [<ms>]
moves         <k> of <total> nodes changed in 700 ms
seam          0 differences at the wrap
paint         card body not repainting, overflow 0 at 375 px
a11y          aria-hidden root, 0 focusable, 0 overlaps
reduced       0 changes in 800 ms, 0 running, artwork visible
gates         <each gate>: pass
```

For reference, the kit's example scene measures: 8 nodes, 10 WAAPI animations, badEasing 0, durations [6000], seam 0, 0 focusable, 0 overlaps, and with `frozen` 0 changes and 0 running.
