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

## Known dependency limitations

At initial publication, GitHub Dependabot reported seven open alerts across
`pyproject.toml` and `uv.lock`, covering four Transformers advisories:

- [GHSA-xrqw-3rrv-vx5w](https://github.com/advisories/GHSA-xrqw-3rrv-vx5w):
  chat-template path traversal; patched in 5.10.0.
- [GHSA-fgcw-684q-jj6r](https://github.com/advisories/GHSA-fgcw-684q-jj6r):
  code execution in the LightGlue loading path; patched in 5.5.0.
- [GHSA-29pf-2h5f-8g72](https://github.com/advisories/GHSA-29pf-2h5f-8g72):
  remote code execution; patched in 5.3.0.
- [GHSA-69w3-r845-3855](https://github.com/advisories/GHSA-69w3-r845-3855):
  code execution in `Trainer`; patched in 5.0.0rc3.

The experiment runtime currently requires Transformers 4.x. Moving to a patched
5.x release needs a separately validated compatibility update; passing the
offline tests does not resolve these advisories. Historical result files remain
evidence of their recorded runtime, even after a future dependency upgrade.

The loader uses pinned revisions, safetensors and `trust_remote_code=False`.
Those choices are not a claim that the dependency vulnerabilities are fixed.
Do not use this environment to load untrusted models or checkpoints. Check the
[current alerts](https://github.com/vinays75-coder/privmark-research/security/dependabot)
for updated status. Alerts remain open; no dismissals or exceptions were applied.

## Safe handling

Keep the dashboard bound to localhost unless you have added deployment controls.
Use fictional records for experiments. Review artifacts before publishing: raw
prompts and responses are intentionally retained. Never enable untrusted model
remote code or replace pinned model revisions silently. See `.gitignore` for
excluded secrets, caches, model weights and personal notes.
