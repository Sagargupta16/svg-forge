---
type: regex
pattern: '<picture\b(?=[\s\S]*?min-width:\s*1012px)(?=[\s\S]*?srcset=["''][^"'']*stats\.svg["''])(?=[\s\S]*?<img\b[^>]*src=["''][^"'']*stats-mobile\.svg["''])[\s\S]*?</picture>'
---

The reply gives a `<picture>` whose `<img>` is the phone card and whose `(min-width: 1012px)` source swaps in the desktop card.
