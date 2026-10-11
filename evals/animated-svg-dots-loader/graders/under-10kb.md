---
type: regex
pattern: '^[\s\S]{10240}'
match: not_contains
target:
  source: file
  path: loading.svg
---

A three-dot loader stays under 10 KB.
