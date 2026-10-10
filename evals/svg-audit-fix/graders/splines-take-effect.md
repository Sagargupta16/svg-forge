---
type: regex
pattern: '<(?![^>]*\bcalcMode=["'']spline["''])[^>]*\bkeySplines='
match: not_contains
target:
  source: file
  path: card.svg
---

Every element with keySplines has calcMode="spline". Mirrors validate_svg.py SV018.
