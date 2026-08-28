## What does this PR do?

<!-- Briefly describe the change and the problem it solves. -->

## Types of changes

- [ ] New skill (`skills/<name>/`)
- [ ] New/modified hook rule (`hooks/posttooluse.py`)
- [ ] CLAUDE.md rule change
- [ ] CLI / packaging (src/, npm/, pyproject.toml)
- [ ] CI / GitHub Actions
- [ ] Docs (README, CHANGELOG, docs/)
- [ ] Other

## Checklist

- [ ] I read the [Contributing Guide](../CONTRIBUTING.md).
- [ ] New skills: `SKILL.md` (frontmatter + trigger description) and
  `references/code-guide.md` exist; the routing table in `CLAUDE.md` and the
  skill table in `README.md` are updated.
- [ ] Hook rules: I added a matching test case and it keeps the existing
  false-positive rate intact (see `docs/` for the case-sensitivity
  convention).
- [ ] I bumped the version in all three places if this is a release-ready
  change: `plugin.json` / `src/drogon_plugin/__init__.py` / `npm/package.json`.
- [ ] `drogon-claude-plugin verify` passes locally (or CI green).

## Test plan

- [ ] Local verification commands used: `______`
- [ ] CI / smoke tests: `______`

## Screenshots (if UI / terminal output changed)

- ...

## Related issues

- Closes #______