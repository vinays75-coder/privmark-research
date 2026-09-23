"""Check the Git index for accidental credentials, caches and large temporary files."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {'.venv', '__pycache__', '.pytest_cache', '.ruff_cache', '.cache',
                   'node_modules', '.codex', '.agents', '.idea'}
FORBIDDEN_SUFFIXES = {'.pyc', '.pyo', '.tmp', '.temp', '.log', '.safetensors', '.gguf',
                      '.pt', '.pth', '.ckpt', '.bin'}
SECRET_PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
    re.compile(rb'AKIA[0-9A-Z]{16}'),
    re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}'),
]


def main():
    listed = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).split(b'\0')
    paths = [Path(p.decode()) for p in listed if p]
    failures = []
    for path in paths:
        name = path.name
        if (set(path.parts) & FORBIDDEN_PARTS or path.suffix.lower() in FORBIDDEN_SUFFIXES
                or name in {'.DS_Store', 'secrets.toml', 'CONVERSATION_HANDOFF.md'}
                or (name.startswith('.env') and name != '.env.example')):
            failures.append(f'Excluded local file is tracked: {path}')
        # Inspect the staged bytes, not a possibly different working tree.
        payload = subprocess.check_output(['git', 'show', f':{path.as_posix()}'], cwd=ROOT)
        if len(payload) > 10 * 1024 * 1024:
            failures.append(f'Unexpected file larger than 10 MiB: {path}')
        if any(pattern.search(payload) for pattern in SECRET_PATTERNS):
            failures.append(f'Possible credential/private key in {path}; inspect locally')
    if failures:
        raise SystemExit('\n'.join(failures))
    if not paths:
        raise SystemExit('No tracked files; stage the intended repository first.')
    print(f'Checked {len(paths)} tracked files: no forbidden local files or recognized secret patterns.')
    print('Pattern scanning is a safeguard, not a guarantee that all sensitive data is detected.')


if __name__ == '__main__':
    main()
