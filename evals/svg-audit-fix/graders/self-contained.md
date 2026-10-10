---
type: regex
pattern: '<script\b|<foreignObject\b|@import\b|javascript:|\b(?:href|src)\s*=\s*["''](?!#|data:)|url\((?!\s*["'']?(?:#|data:))|\son[a-z]+\s*=\s*["'']'
flags: i
match: not_contains
target:
  source: file
  path: card.svg
---

Nothing loads from outside the file and nothing runs: no script, foreignObject, event handler, @import, or href, src or url() other than #id and data:. Mirrors validate_svg.py SV005 to SV009 for the standalone target (GitHub's image proxy).
