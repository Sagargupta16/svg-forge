---
type: regex
pattern: '^(?=[\s\S]*>\s*1,284\s*<)(?=[\s\S]*>\s*312\s*<)(?=[\s\S]*>\s*4\.9k\s*<)(?=[\s\S]*>\s*98%\s*<)'
target:
  source: file
  path: assets/stats.svg
---

Every value from the JSON is drawn as text, exactly as given.
