# Security policy

This is a research prototype, not a certified privacy control or production
service. The supplied `PM-...` values are synthetic test secrets, not credentials.
The reported context-disclosure failures are known experimental findings.

## Reporting vulnerabilities

Use [GitHub private vulnerability reporting](https://github.com/vinays75-coder/privmark-research/security/advisories/new)
for vulnerabilities in this repository. Do not place credentials, real personal
data or sensitive exploit details in a public issue. If private reporting is
unavailable, request a private reporting channel from the maintainer without
posting the sensitive details.

The maintained version is the current `main` branch. There is no guaranteed
response time or supported production deployment. Model behavior, third-party
packages and external evidence require their own assessment.

## Safe handling

Keep the dashboard bound to localhost unless you have added deployment controls.
Use fictional records for experiments. Review artifacts before publishing: raw
prompts and responses are intentionally retained. Never enable untrusted model
remote code or replace pinned model revisions silently. See `.gitignore` for
excluded secrets, caches, model weights and personal notes.
