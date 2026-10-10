---
type: regex
pattern: '^(?=[\s\S]*\bcache\b)(?=[\s\S]*\b(?:db|database|origin)\b)(?=[\s\S]*\b(?:miss|hit)\b)'
flags: i
target:
  source: file
  path: src/scenes/CacheScene.tsx
---

The scene names the mechanism's own parts: a cache, a database and a miss or hit.
