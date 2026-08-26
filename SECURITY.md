# Security Policy

## Scope

AIRSI AlgoTrader is public education and research software for paper trading and strategy analysis. It is not a production trading service, custody system, financial product, or source of investment advice.

## Supported versions

Only the `main` branch and the latest commit are actively reviewed. Historical commits and forks may contain known defects and must not be used as a live-trading deployment without an independent security review.

## Reporting a vulnerability

Please do not open a public issue for a suspected credential leak, authentication bypass, remote-code-execution issue, workflow privilege escalation, or exchange-control defect. Use GitHub’s private vulnerability reporting feature for this repository when available. If that feature is unavailable, contact the repository owner privately through the GitHub profile and include the affected file, a minimal reproduction, impact, and a proposed mitigation. Do not include live exchange keys, API tokens, or personal data in the report.

The maintainer will acknowledge a credible report, investigate it, and publish a fix or mitigation when appropriate. Reports involving an exposed credential should be treated as urgent: revoke and rotate the credential with the relevant provider before discussing repository history.

## Safe disclosure boundaries

Security research must be limited to this repository and test infrastructure that you own or are explicitly authorized to assess. Do not probe exchanges, GitHub infrastructure, third-party APIs, or another person’s account. Do not use this project to mine cryptocurrency, spam services, bypass access controls, or automate unauthorized trading.

## Secret handling

Never commit `.env` files, exchange credentials, Telegram tokens, AI provider keys, private keys, or generated live configuration. Use GitHub Actions secrets only for future automation that has a clearly documented need, and grant the workflow the minimum required permissions. The CI workflow intentionally has no exchange or provider secrets.
