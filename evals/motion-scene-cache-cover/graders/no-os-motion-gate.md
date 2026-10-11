---
type: regex
pattern: 'useReducedMotion|prefers-reduced-motion|reducedMotion\s*=\s*\{?\s*["'']user'
match: not_contains
target:
  source: file
  path: src/scenes/CacheScene.tsx
---

Adds no OS-level reduced-motion gate: the app has its own motion setting, and motion stays visible by default.
