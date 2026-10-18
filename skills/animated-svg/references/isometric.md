# Isometric line figures

Hero and cover art as line figures: rounded solids drawn in one stroke width on a filled plate, seen from a 2:1 isometric view, with one bright edge saying where to look. The look reads at thumbnail size, costs almost nothing to animate, and never depends on a hue, so it survives both GitHub themes. These rules are distilled, in SMIL and CSS terms, from the hairline project (https://github.com/lucasmarkes/hairline, MIT), which wrote them for pointer-driven React figures; its README and `skills/hairline-create/rules.md` are the source for every number quoted here.

Use it for a README header or social image that shows an object (a tray of cards, a rack of blades, a field of pillars, a stack of frames), for an empty state, or for a mark rebuilt as a solid. Diagrams with boxes and arrows stay with the `flow` kind.

## 1. The projection

World space is x and y on the ground, z up. The camera turns the ground by an azimuth and tilts it: with `az = 45deg` and `k = sin(elevation) = 0.5` the view is the classic 2:1 isometric, and nothing in it depends on the viewport.

```python
import math

AZ, K = math.radians(45), 0.5
C, S, ZF = math.cos(AZ), math.sin(AZ), math.sqrt(1 - K * K)


def project(x, y, z, scale=1.9, ox=200, oy=166):
    X = x * C - y * S
    Y = x * S + y * C
    return ox + scale * X, oy + scale * (Y * K - z * ZF)
```

- There is no perspective and no hidden-line removal: plates are filled with the ground color and painted back to front, so a nearer one simply covers.
- Fit the camera to the most extreme pose, not the rest pose: project the lifted points too and center their bounding box, so nothing leaves the frame at the far end of the motion.
- Two decimals are enough for a hairline at any zoom and keep path strings short.

## 2. A solid is a silhouette and one crease

- Round every corner, then draw less. A solid is the convex hull of two rounded rings, its top at `z1` and its base at `z0`, drawn as one closed path. The vertical corners are never drawn; the eye fills them in.
- The only inner line is the crease: the camera-facing run of a ring inset one or two units on the lid. It reads as a bevel.
- A thin plate gets a second line for its thickness, not a second solid. A tapering solid (a cabin, a roof) is the hull of its foot ring and its smaller top ring.
- Rounded rings: sample each corner in four steps (sixteen sides for a full round); past about 20 px of radius on screen use more.
- Rejected: a box with twelve edges, any vertical corner line, a sharp corner, inner lines as bright as the silhouette.

## 3. One stroke, four weights, a filled plate

| Token | Dark page | Light page | Use |
| --- | --- | --- | --- |
| plate | `#08090a` | `#ffffff` | the fill of every solid: the color the figure sits on |
| hi | `#d0d6e0` | `#232327` | what is lit: one place at a time |
| edge | `#5b5d64` | `#a4a4ac` | silhouettes |
| mid | `#3e3e44` | `#c3c3c9` | every other stroke |
| lo | `#29292d` | `#e0e0e4` | what recedes: creases, far guides |

- One stroke width, 0.9 to 1.2 px at the drawn size, `stroke-linejoin="round" stroke-linecap="round"`. In a file that scales through its viewBox, pick the width in user units for the size it is shown at. `vector-effect="non-scaling-stroke"` keeps hairlines even on the `web` target, but never on a path that also animates `pathLength` or a dash (SV019).
- With forge themes: plate = `bg` (or `card` for a raised panel), hi = `ink`, edge = `text`, mid = `dim`, lo = `panel_stroke`. The plate must be the page color under the figure, because a plate hides what is behind it; a transparent plate shows every far edge.
- No fills but the plate, no gradients, glows, shadows or second hue. The stroke is the only highlight: the active edge goes from `edge` to `hi` and nothing else changes color, so the color reads as information.
- Both pages: the dark and light columns above are the two halves of a `<picture>` pair, each checked with `--theme dark` or `--theme light`.

## 4. Rest is designed, never flat

The still frame is the thumbnail, the link preview and what a static renderer draws. Give every part a rest value that is not zero and not uniform: a field of pillars rests as a dune with two rises, a tray of cards leans back 12 degrees and one card stands a little proud. Put one bright mark at rest where the eye should start. An empty state shows the object holding nothing, and the object itself is composed, uneven and whole. Rejected: a flat grid, a regular row, an empty tray because nothing was drawn in it, a rest that looks like nothing rendered yet.

## 5. One highlight

At rest one mark is bright. When a beat chooses a part, the bright goes to it and the rest mark gives it up. One highlight may cover the parts of one thing (a tray's rim and its beads) but it marks one place and means one thing. In SMIL, swap the stroke token on both elements on the same clock:

```xml
<path d="..." stroke="#5b5d64">
  <animate attributeName="stroke" values="#5b5d64;#d0d6e0;#d0d6e0;#5b5d64"
           keyTimes="0;0.3;0.6;0.65" dur="6s" repeatCount="indefinite"/>
</path>
```

The 260 ms a stroke takes to cross-fade in an app becomes a keyTimes gap here: `0.3` to `0.345` on a 6 s clock is about 270 ms.

## 6. Construction stays honest

Paint back to front: walk a grid diagonal by diagonal from the far corner, and sort free solids by `x + y` in world space. A solid that must hide what is behind it keeps its plate fill. Dashed guides and links are painted before the plates they belong to. When a beat changes depth order (a card stands up in front of its neighbors), place the element in document order for that moment; do not fade one copy out and another in. Rejected: a far edge showing through a near solid, a guide crossing the face of its own plate, a paint order that is the order the code happened to make things in.

## 7. The clock stands in for the pointer

In an app these figures answer the pointer; an `<img>` gets none, so the clock plays the hand. Write the tour as the storyboard: three to six stops on different parts, in the order a hand would reach them, each a beat where one part answers and the highlight moves to it, then a return to rest. A lap is a sentence, not an inventory: three stops that each show a different answer beat a tour of every part.

- **Lift** a solid: a rise in z is a pure vertical move on screen, `scale * z * sqrt(1 - k^2)` px, so `animateTransform type="translate"` on the solid's group reads as a lift. Growth (a pillar getting taller) changes the hull, so morph `d` with SMIL and equal point counts in every value.
- **Stagger by distance**, not by index: `delay = |i - a| x step` with a step of 30 to 60 ms, so the motion spreads out from the part that answered. Items moving in list order whatever was touched is a queue, not a gesture.
- **Clamp the reach**: the answer has a far end and the figure is still composed there. A falloff that reaches a floor (1 at the center, about 0.31 at 42 percent of the radius, 0.09 beyond) keeps a field from flattening.
- **Discrete changes ease out long**: 700 ms on `keySplines="0.32 0.72 0 1"`, the curve a choice between items takes. On the `web` target with a real pointer, a continuous answer (where the pointer is) rides a spring instead, because its target moves every frame; see [../../motion-scene/references/motion.md](../../motion-scene/references/motion.md) section 8.
- **Loop**: a `medium` or `long` preset on one clock; the reset happens while the figure is back at rest, so the seam is invisible.

## 8. No words inside the figure

Geometry carries identity: a punch on a card's tab, a dot code on a crate's lid, a bright edge instead of a label. Names and numbers go to the README text or a caption under the stage, and a figure that cannot be understood without them is not finished. The one exception is a mark rebuilt as the object itself (a company's triangle as a slab that seats on its pad): a glyph that belongs to the mark is a relief on one face, nothing else in that figure is a letter, and if the mark belongs to someone else, say so when handing over.

## 9. Hit areas do not move (web target only)

When the figure answers a real pointer, test the hover against the rest pose, never the pose on screen: an invisible rect over each part's resting footprint carries the `:hover`, the lifted solid does not. Otherwise the geometry lifts out from under the pointer, the hover drops, the solid falls back, and the hover returns: a flicker loop.

## 10. Check it

- The silhouette reads at 240 px wide: `python scripts/frames.py FILE.svg --width 240 --theme both`. You know what you drew, so point at the two or three features that make each part what it is (a cabin narrower than its body, a lantern on a tower); a part that shows none of them is a rounded block.
- Rest is a composition; one place is bright; nothing shows through; nothing leaves the frame at the far end of any beat; both themes read; no words in the drawing.
- Past about a hundred solids, or with parts under ten units, the figure stops reading. A figure that needs more is two ideas.
