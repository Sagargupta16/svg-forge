---
type: regex
pattern: '<picture\b(?=[\s\S]*?prefers-color-scheme:\s*dark)(?=[\s\S]*?banner-dark\.svg)(?=[\s\S]*?banner-light\.svg)[\s\S]*?</picture>'
---

The reply gives a `<picture>` snippet with a dark `<source>` that names both files.
