# Security Policy

## Supported versions

Security fixes are provided for the latest minor release and the current
development branch. Older versions may require an upgrade.

## Reporting a vulnerability

Do **not** open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting for this repository
(**Security → Report a vulnerability**) and include:

- affected version and commit;
- deployment shape (Docker, systemd, Helm, local);
- a minimal reproduction or proof of concept;
- impact and any known mitigations.

You should receive an acknowledgement within a few business days. We will
coordinate a fix and disclosure date, and credit reporters who want credit.

## Security model

- The management API uses JWT sessions; roles are viewer, editor, approver and
  admin. Project membership scopes management operations.
- The public API uses AK/SK HMAC signing with a `Date` window and constant-time
  comparison. SHA-1 compatibility can be disabled.
- Datasource passwords and SK values are encrypted at rest. Never commit a
  real `.env`, a Fernet key or a database dump.
- Outbound HTTP is SSRF-protected: private, loopback and link-local targets are
  blocked by default. Explicit allowlists are required for internal endpoints.
- Datasource DSNs that resolve to the platform's own control database are
  rejected.
- MCP write tools require approval tokens; read tools are scoped to the caller's
  project.
- Audit records cover authentication, publishing, approvals, policy changes,
  MCP calls and administrative actions.

## Dependency and container hygiene

Dependabot and CodeQL run in CI. Container images should be rebuilt from the
release workflow, not from an unreviewed local image. Report a vulnerable
dependency through the same private channel.
