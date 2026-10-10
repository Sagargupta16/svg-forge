---
type: regex
pattern: '<(?=[^>]*\bpathLength=)[^>]*non-scaling-stroke'
match: not_contains
target:
  source: file
  path: card.svg
---

No element combines pathLength with non-scaling-stroke. Mirrors validate_svg.py SV019.
