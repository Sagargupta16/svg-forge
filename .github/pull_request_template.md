## Summary

<!-- 1-3 sentences: what this PR changes and why. -->

## Change type

- [ ] New template or generator option
- [ ] Validator rule
- [ ] Skill or reference content
- [ ] Agent
- [ ] Bug fix
- [ ] Docs / CI / tooling

## Checklist

- [ ] `python scripts/check.py` passes
- [ ] `python -m pytest -q` passes
- [ ] `npx -y @sagargupta1610/skillcheck@0.2.5 lint skills` reports no errors
- [ ] New or changed SVGs pass `validate_svg.py` and were looked at in a browser (and on GitHub if they target READMEs)
- [ ] CHANGELOG.md entry under a concrete version; version bumped in both `.claude-plugin/*.json` files when releasing
- [ ] No en or em dashes, no absolute home paths, no secrets
