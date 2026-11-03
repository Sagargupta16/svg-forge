---
type: regex
pattern: 'font-size(?:=["'']|:\s*)(?:[0-9](?:\.[0-9]+)?|10(?:\.[0-4][0-9]*)?)(?:px)?["''; }]'
match: not_contains
target:
  source: file
  path: assets/stats-mobile.svg
---

No text on the phone card is drawn under 10.5 px, so the labels stay readable at phone width.
