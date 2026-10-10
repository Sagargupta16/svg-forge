---
type: regex
pattern: '^(?=[\s\S]*<text\b[^>]*>(?:\s*<tspan\b[^>]*>)?[^<]*\bpush\b)(?=[\s\S]*<text\b[^>]*>(?:\s*<tspan\b[^>]*>)?[^<]*\bbuild\b)(?=[\s\S]*<text\b[^>]*>(?:\s*<tspan\b[^>]*>)?[^<]*\btest)(?=[\s\S]*<text\b[^>]*>(?:\s*<tspan\b[^>]*>)?[^<]*\bdeploy)'
flags: i
target:
  source: file
  path: docs/pipeline.svg
---

Each of the four stages is a labelled node: push, build, test and deploy appear as `<text>` content.
