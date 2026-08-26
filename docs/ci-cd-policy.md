# CI/CD and GitHub Policy

## Purpose

This repository uses GitHub Actions for continuous validation and release-readiness checks. It does not automatically deploy a live bot, connect to an exchange, publish trading signals, or mutate strategy code. This boundary is intentional: the project remains education and research software rather than an unattended financial service.

## Checks on future changes

| Workflow            | Trigger                                                    | What it checks                                                                                                                                     | Privilege boundary                                                                         |
| ------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `CI`                | Pushes to `main` and pull requests to `main`               | Python compilation/tests, frozen dependency installation, TypeScript typechecks, API/dashboard builds                                              | `contents: read`; no secrets; GitHub-hosted runners; persisted Git credentials disabled    |
| `Repository policy` | Pushes to `main`, pull requests to `main`, manual dispatch | Credential-pattern scan, education/license files, action SHA pinning, no privileged triggers, no self-hosted runners, no exchange-control commands | `contents: read`; deterministic local script; no network credentials                       |
| `Dependency review` | Pull requests to `main`                                    | Fails on high-severity dependency changes                                                                                                          | `contents: read`, `pull-requests: read`; no comments or write access                       |
| `CodeQL`            | Pushes, pull requests, weekly schedule, manual dispatch    | JavaScript/TypeScript and Python security analysis                                                                                                 | `contents: read`, `actions: read`, `security-events: write` only for code-scanning results |
| Dependabot          | Weekly                                                     | Opens dependency update pull requests for pip, npm, and GitHub Actions                                                                             | No exchange or provider secrets are configured                                             |

All third-party Actions are pinned to full commit SHAs. Workflows do not use `pull_request_target`, `workflow_run`, self-hosted runners, or exchange-control commands. GitHub-hosted runners are used because public pull requests can contain untrusted code.

## GitHub repository settings to review

The repository is public, has a detectable MIT license, and now includes `README.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, and `SECURITY.md`. At the time of this change, GitHub reported that Actions were enabled, repository-level branch protection was not configured, and repository push protection/security-policy status was not enabled. These are repository settings, not account-profile changes.

For stronger future protection, the owner should review the repository’s Actions settings and choose a policy that permits only trusted GitHub Actions used here. The owner should also enable “Require actions to be pinned to a full-length commit SHA” if available, enable secret scanning/push protection where the plan permits, and protect `main` by requiring the `CI`, `Repository policy`, `Dependency review`, and `CodeQL` checks before merge. Do not add exchange, Telegram, AI-provider, or personal GitHub credentials to CI unless a future workflow has a documented need, least-privilege permissions, and human review.

## Education-only and GitHub policy boundary

The repository’s MIT license remains the standard software license and is intentionally not modified with extra restrictions that could make it non-standard. The separate education-only notice supplies the project-purpose, risk, and non-advice language. This separation preserves license clarity while making the intended use prominent.

The source and workflows are designed to avoid prohibited platform behavior such as spam, cryptocurrency mining, unauthorized access, credential publication, deceptive performance claims, or excessive automated activity. GitHub’s policies still apply to every user and future contribution; this document is not legal advice or a guarantee that GitHub will approve any future content.

## References

[1]: https://docs.github.com/en/actions/reference/security/secure-use "GitHub Actions secure use reference"
[2]: https://docs.github.com/actions/security-guides/using-secrets-in-github-actions "Using secrets in GitHub Actions"
[3]: https://docs.github.com/en/code-security/concepts/secret-security/push-protection "GitHub push protection"
[4]: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories "GitHub public repository community profiles"
[5]: https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies "GitHub Acceptable Use Policies"
