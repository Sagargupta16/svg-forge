---
type: regex
pattern: 'prefers-color-scheme'
match: not_contains
target:
  source: file
  path: assets/banner-light.svg
---

The light file does not switch themes inside itself.
