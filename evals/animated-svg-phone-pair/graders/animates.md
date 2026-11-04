---
type: regex
pattern: '<animate(?:Transform|Motion|Color)?\b|<set\b|@keyframes\b'
target:
  source: file
  path: assets/stats-mobile.svg
---

The file animates with SMIL or CSS.
