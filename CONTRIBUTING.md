# Contributing

PrivMark is an exploratory privacy disclosure framework. Read the [research
scope](README.md) and [experiment guide](docs/EXPERIMENT_12_RECORDS.md) before
changing measurements or claims. Keep changes small and explain their purpose.

## Local development

Use Python 3.11–3.13 and uv:

```bash
uv sync --locked --extra exports
uv run --no-sync python -m ruff check .
uv run --no-sync python -m pytest -q
uv run --no-sync python scripts/verify_evidence.py
uv run --no-sync python scripts/check_repository.py
```

Tests use offline fixtures and test doubles. They do not run pretrained models.
Live experiments require an explicit, bounded plan; do not run inference in CI.
Never submit real private records, credentials, model weights or environment files.

## Pull requests

Create a branch and open a pull request against `main`. Describe the problem,
behavioral change, validation and scientific limitations. CODEOWNERS assigns
`@vinays75-coder`. CI must pass. Keep model comparisons matched and distinguish
answer content, format, disclosure, truncation and unknown evidence.

Measured files in `results/` are immutable evidence. Do not reformat or overwrite
them; hashes refer to exact bytes. Add new runs under a new reviewed path and
explicitly adjust `.gitignore` only when that evidence should be published. Most
new local results are intentionally ignored. A hash establishes content integrity,
not truthfulness or independent scientific validation.

Keep dependencies locked with uv. Dependency changes can affect reproducibility;
record the environment and do not imply historical runs used current versions.

The original abstract is the author's reference text. Propose manuscript changes
separately rather than silently rewriting `docs/paper-abstract.txt`.
