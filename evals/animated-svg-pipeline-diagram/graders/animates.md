---
type: regex
pattern: '<animate(?:Transform|Motion|Color)?\b|<set\b|@keyframes\b'
target:
  source: file
  path: docs/pipeline.svg
---

The file animates with SMIL or CSS.
