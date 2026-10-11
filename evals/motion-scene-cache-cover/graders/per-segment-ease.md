---
type: regex
pattern: '\btimes\s*:\s*\[[^\]]*,[^\]]*,[^\]]*\][^{}]{0,300}?\bease\s*:\s*["'']|\bease\s*:\s*["''][^"'']*["''][^{}]{0,300}?\btimes\s*:\s*\[[^\]]*,[^\]]*,'
match: not_contains
target:
  source: file
  path: src/scenes/CacheScene.tsx
---

No single ease string next to a `times` array of three or more keyframes: multi-keyframe tracks use per-segment ease arrays, or WAAPI drifts them off the storyboard.
