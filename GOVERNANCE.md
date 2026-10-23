# Governance

OpenDataFusion is maintained by the project maintainers listed in
[CODEOWNERS](CODEOWNERS). This document explains how decisions, releases and
access are handled.

## Decisions

- Small changes are decided in pull request review.
- Larger changes start as an issue or discussion with the problem statement,
  alternatives and operational impact.
- Maintainers seek rough consensus. If consensus is not reached, the
  maintainers decide by simple majority; the reason is recorded in the issue.
- A maintainer with a conflict of interest recuses themselves.

## Maintainers

- Review and merge changes, triage issues and manage releases.
- Are expected to follow the Code of Conduct and the security policy.
- Are added by consensus of existing maintainers after sustained, constructive
  contributions.
- Can step down at any time. Inactive maintainers may be moved to emeritus
  status after a reasonable period.

## Releases

- Semantic versioning. Breaking changes require a major release and a migration
  note.
- Release notes are generated from merged changes and reviewed by a maintainer.
- Container images are published by the release workflow from a signed tag.
- Security fixes may be released outside the normal cadence.

## Repository access

Write access is limited to maintainers. Branch protection on `main` requires a
pull request, passing CI, a review and no unresolved conversations. Force
pushes and direct commits to `main` are disabled.
