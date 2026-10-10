---
type: regex
pattern: 'SV008|extern|image proxy|camo|remote (?:image|url|resource|request)|network request'
flags: i
---

Finds the external `<image href=https://...>` that GitHub's image proxy blocks.
