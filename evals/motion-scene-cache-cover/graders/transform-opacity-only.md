---
type: regex
pattern: '\b(?:animate|initial|exit|whileInView|whileHover|whileTap)\s*=\s*\{\{[^}]*\b(?:width|height|top|left|right|bottom|filter|boxShadow)\s*:'
match: not_contains
target:
  source: file
  path: src/scenes/CacheScene.tsx
---

Animates transform and opacity only, never layout or paint properties.
