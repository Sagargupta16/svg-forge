---
type: regex
pattern: '\bcalcmod\s*='
match: not_contains
target:
  source: file
  path: card.svg
---

The misspelled `calcmod` attribute is gone.
