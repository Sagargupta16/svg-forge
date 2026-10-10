---
type: regex
pattern: '<animateMotion\b|<mpath\b|type=["'']translate["'']|offset-path|@keyframes[^{]*\{[\s\S]*?translate'
flags: i
target:
  source: file
  path: docs/pipeline.svg
---

Something moves between stages (motion along a path or a translate), not only a fade or a color change.
