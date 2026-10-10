---
type: regex
pattern: '^[\s\S]{51200}'
match: not_contains
target:
  source: file
  path: assets/stats.svg
---

The file is under 50 KB, the skill's budget for README images (validate_svg.py SV013 stops at 100 KB).
