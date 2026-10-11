---
type: regex
pattern: '<svg\b[^>]*\brole=["'']img["''][\s\S]*?<title\b[^>]*>\s*[^<\s]'
target:
  source: file
  path: card.svg
---

Root has role="img" and a non-empty `<title>`. Mirrors validate_svg.py SV010.
