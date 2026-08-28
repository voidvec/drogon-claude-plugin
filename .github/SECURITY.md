# Security Policy

## Reporting a Vulnerability

For **security-related report**, please do **not** open a public issue or
discussion — some vulnerabilities are easier to exploit once they are known.

Instead, contact the maintainers privately:

- **GitHub advisory**: use the
  [Report a vulnerability](https://github.com/voidvec/drogon-claude-plugin/security/advisories/new)
  form on the repository, or
- **Email**: `luca@c0ding.cc`

We try to acknowledge reports within **3 working days** and are happy to credit
contributors in the advisory once a fix is released.

## Scope

This project ships:

- plugin **rules** (`CLAUDE.md`) and **skills** (`skills/`) that instruct an AI
  assistant how to write Drogon C++ code;
- ESLint-style **detection hooks** (`hooks/`) that flag suspicious patterns;
- CLI **installer** packages on PyPI and npm.

The most security-relevant code is `hooks/posttooluse.py`, which executes on
every edit the assistant writes. If it ever executes content from the file
being scanned (besides the pure regex matching), that is a critical
vulnerability.

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Responsible disclosure

We appreciate responsible disclosure: giving us reasonable time to fix and
release before publicizing. We apply the fix to a patch release and publish a
GitHub advisory after 30 days or at the user's discretion.