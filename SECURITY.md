# Security Policy

## What this plugin is

svg-forge ships Markdown skills, a subagent definition, starter SVG files and small Python scripts (standard library only) that generate and validate SVG. It has no server and no network calls.

Realistic concerns:

1. **SVG is code-adjacent.** An SVG can carry `<script>`, event handler attributes, external references or `<foreignObject>` HTML. The validator flags all of these; generated output never contains them.
2. **Skill content** can instruct Claude to run commands. A bad or injected skill body could nudge Claude toward harmful actions.
3. **Manifests** (`.claude-plugin/*.json`) could declare unexpected components if the repo were compromised.

## Reporting a vulnerability

Do not open a public Issue or PR. Email **sg85207@gmail.com** with the subject `[svg-forge security]`: what you found, how to reproduce it, the impact, and any suggested fix. Expect a first response within 7 days.

## In scope

- An SVG the validator passes that executes script or loads a remote resource when rendered.
- A generator option that lets user input break out of an attribute or text node (XML injection).
- A skill body that reliably steers Claude past the user's safety checks.
- Secrets committed to the repo.
