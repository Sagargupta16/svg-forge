---
type: regex
pattern: '<img\b[^>]*assets/header\.svg|!\[[^\]]+\]\([^)\s]*assets/header\.svg'
---

The reply hands back README markup that shows the file as an image with alt text (inline `<svg>` is stripped from GitHub Markdown).
