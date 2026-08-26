# Dependency security audit

## Audit scope

On 2026-08-26, the repository was audited across the pinned Python requirements, the complete installed Python environment, the pnpm workspace lockfile, production dependencies, and development dependencies. The audit used `pip-audit 2.10.1` and pnpm’s registry-backed audit command. No credentials or exchange connections were used.

## Findings and remediation

| Surface                           | Initial result                                                                                                                                                   | Remediation                                                           | Current result                                   |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------ |
| Python requirements               | No known vulnerabilities                                                                                                                                         | No package change required                                            | `pip-audit -r bot/requirements.txt` passes       |
| Full installed Python environment | No known vulnerabilities across 111 installed package records                                                                                                    | No package change required                                            | `pip-audit` passes                               |
| pnpm production graph             | `qs@6.15.1` moderate DoS and `body-parser@2.2.2` low DoS                                                                                                         | Added safe workspace overrides to `qs@6.15.2` and `body-parser@2.3.0` | `pnpm audit --prod` reports zero vulnerabilities |
| pnpm complete graph               | 20 advisory records across development tooling, including Vite, esbuild, js-yaml, markdown-it, linkify-it, fast-uri, brace-expansion, postcss, nanoid, and Babel | Added patched-version overrides and regenerated `pnpm-lock.yaml`      | Full `pnpm audit` reports zero vulnerabilities   |

The development advisories were primarily in local build, documentation-generation, and Windows development-server paths rather than the deployed API runtime. They were still remediated because the repository’s CI and code-generation toolchain are part of the maintained attack surface.

## Current commands

Run these from the repository root after installing dependencies:

```bash
source venv/bin/activate
pip-audit -r bot/requirements.txt --progress-spinner off
pip-audit --progress-spinner off
pnpm install --frozen-lockfile
pnpm audit --prod
pnpm audit --audit-level high
```

The mandatory CI workflow now runs the Python audit and a high-severity pnpm production audit on future changes. Dependabot and dependency-review provide additional update and pull-request checks. The workspace keeps a minimum package release age and full lockfile integrity checks; do not bypass those controls for convenience.

## Limitations

A clean audit is a point-in-time result, not a guarantee that future releases, unreviewed code, compromised registries, operating systems, exchange APIs, or runtime configuration are safe. Review Dependabot pull requests, keep the lockfile committed, and re-run both auditors after dependency or toolchain changes. The build still reports a non-security chunk-size warning for the dashboard; it is not treated as a vulnerability.

## References

[1]: https://pypi.org/project/pip-audit/ "pip-audit project"
[2]: https://github.com/pnpm/pnpm/blob/main/docs/cli/audit.md "pnpm audit documentation"
[3]: https://github.com/advisories/GHSA-q8mj-m7cp-5q26 "qs advisory"
[4]: https://github.com/advisories/GHSA-v422-hmwv-36x6 "body-parser advisory"
[5]: https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/about-dependabot-security-updates "GitHub Dependabot security updates"
