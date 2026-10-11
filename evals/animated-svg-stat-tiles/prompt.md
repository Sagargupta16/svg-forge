---
description: 'Stat tiles generated from pasted JSON, with the numbers in the file and alt text.'
tags: [animated-svg]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Turn these numbers into animated stat tiles for my GitHub profile README and save them as `assets/stats.svg`:

```json
[
  {"label": "commits", "value": "1,284"},
  {"label": "pull requests", "value": "312"},
  {"label": "stars", "value": "4.9k"},
  {"label": "test coverage", "value": "98%"}
]
```

Then give me the README markup for it.
