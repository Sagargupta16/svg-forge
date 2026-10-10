---
type: regex
pattern: '<animate(?:Transform|Motion|Color)?\b|<set\b|@keyframes\b'
target:
  source: file
  path: logo-animated.svg
---

The file animates with SMIL or CSS.
