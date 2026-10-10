---
type: regex
pattern: '<animate|<set\b|@keyframes|animation\s*:'
match: not_contains
target:
  source: file
  path: logo.svg
---

`logo.svg` is still static.
