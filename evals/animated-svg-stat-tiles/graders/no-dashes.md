---
type: regex
pattern: '[\u2013\u2014]'
match: not_contains
target:
  source: file
  path: assets/stats.svg
---

No en or em dash characters (U+2013, U+2014). Mirrors validate_svg.py SV014.
