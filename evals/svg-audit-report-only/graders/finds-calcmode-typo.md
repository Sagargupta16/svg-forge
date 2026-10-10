---
type: regex
pattern: 'SV018|calcmod(?!e)|(?:misspel|typo)[^\n]{0,80}calcMode|calcMode[^\n]{0,80}(?:misspel|typo)'
flags: i
---

Finds the `calcmod` typo that silently drops the keySplines easing.
