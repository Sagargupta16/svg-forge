---
type: regex
pattern: 'from\s+["''](?:motion/react|[^"'']*primitives)["'']'
target:
  source: file
  path: app/components/GatewayHero.tsx
---

Animates with Motion: imports `motion/react`, or the skill's copy-in kit primitives that wrap it.
