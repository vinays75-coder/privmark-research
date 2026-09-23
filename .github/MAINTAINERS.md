# Repository settings

Owner: `vinays75-coder`. Default branch: `main`.

The desired protection policy is stored in `branch-protection.json`: pull requests,
the up-to-date `Offline checks` status, resolved conversations and linear history
are required. Force pushes and deletion are disabled; administrators are included.
CODEOWNERS assigns all paths to the owner.

This repository initially has one confirmed maintainer. Required approving review
count is zero, and code-owner approval is not mandatory, so the owner can merge
an own pull request after checks. GitHub does not allow authors to approve their
own pull requests. Once another reviewer with write access is available, set the
required count to one and enable required code-owner review if appropriate.

Squash merging is enabled, merge commits and rebase merging are disabled, and
merged branches are deleted automatically. Dependency alerts and private
vulnerability reporting should be enabled. The workflow token has read-only
permissions, and third-party Actions are pinned to commit hashes.

Apply the policy after the initial commit and CI context exist:

```bash
gh api --method PUT repos/vinays75-coder/privmark-research/branches/main/protection \
  --input .github/branch-protection.json
```

A policy file is not evidence of remote enforcement: confirm the actual GitHub
settings after applying it. Do not weaken checks or edit experiment state just
to get a failing change merged.
