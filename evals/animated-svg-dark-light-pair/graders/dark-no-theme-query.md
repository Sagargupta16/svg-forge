---
type: regex
pattern: 'prefers-color-scheme'
match: not_contains
target:
  source: file
  path: assets/banner-dark.svg
---

The dark file does not switch themes inside itself (that follows the OS, not GitHub, and fails on WebKit).
