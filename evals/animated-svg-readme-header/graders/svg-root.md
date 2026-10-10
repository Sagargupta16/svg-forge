---
type: regex
pattern: '<svg\b(?=[^>]*\bxmlns=["'']http://www\.w3\.org/2000/svg["''])(?=[^>]*\bviewBox=["''][^"'']*\d)'
target:
  source: file
  path: assets/header.svg
---

Root is an `<svg>` in the SVG namespace with a viewBox. Mirrors validate_svg.py SV002 to SV004.
