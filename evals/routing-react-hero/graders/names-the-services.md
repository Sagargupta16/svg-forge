---
type: regex
pattern: '^(?=[\s\S]*\bauth\b)(?=[\s\S]*\bbilling\b)(?=[\s\S]*\bsearch\b)'
flags: i
target:
  source: file
  path: app/components/GatewayHero.tsx
---

The scene shows the three services the user named.
