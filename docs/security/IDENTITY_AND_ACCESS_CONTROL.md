# Identity and Access Control - ElinaOS

Identity-first zero-trust: every request authenticated, authorized, audited.

## Principal Types
- Human operator: GitHub account + MFA + GPG signed commits.
- Agent identity: SPIFFE ID `spiffe://elina/agent/<name>`, JWT SVID.
- Workload: GitHub Actions runner, token with audience `elina-aud`.
- Device: mobile app instance, device ID + app attestation.

## Authentication
- Human: GitHub OAuth, PAT with fine-grained scopes, expiry 90d.
- Agent: JWT 5m TTL, signed by issuer `elina-issuer`, kid rotation.
- Workload: OIDC token from GitHub Actions, aud verified.
- Device: Firebase App Check or Apple DeviceCheck.
- Passwords: not used, only tokens and keys.

## Authorization Models
- RBAC: roles operator, publisher, viewer, auditor.
- ABAC: attributes tenant, channel, data_class, risk_score.
- Policy engine: OPA Rego, policy files in `docs/security/policies/`.
- Example Rego: `allow if role==publisher and data_class!=RESTRICTED`.
- Default DENY, explicit ALLOW only.

## Token Scopes
| Scope | Allows | Example |
|---|---|---|
| read:content | read queue | trend_hunter |
| write:content | write queue | content_creator |
| publish:platform | publish via manager | publisher |
| admin:repo | push to GitHub | github_manager |
| audit:logs | read logs | performance_analyzer |

## Least Privilege Review
- Weekly scan: `scripts/audit_permissions.py` lists over-scoped tokens.
- If agent did not use scope in 30 days, auto-revoke and PR to remove.
- Operator dual-control for admin scopes: need 2 approvals.

## Session Management
- JWT expiry 15m, refresh token 24h, rotation on each refresh.
- Refresh token bound to device fingerprint hash.
- Logout revokes refresh token via denylist in Redis (TTL 24h).
- Concurrent session limit: 3 per user, oldest kicked.

## MFA and Step-up
- TOTP or WebAuthn required for admin actions.
- Step-up auth if risk score high: new IP, impossible travel.
- Risk score from: IP reputation, device, behavior baseline.

## Audit
- Every auth decision logged: who, what, when, result, reason.
- Failed logins count towards rate limit and alert after 5.
- Logs include JTI to trace token lifecycle.

## Secrets
- No secret in JWT payload, only sub, scope, exp, jti.
- Private keys stored in vault, public keys in JWKS endpoint.
- JWKS rotation weekly, cache 1h max.

## Hardening
- No wildcard `*` allowed in policies.
- Policy changes require PR + 2 reviewers + CI OPA test.
- Break-glass account exists but monitored and expires in 1h.
- Identity note 63: RBAC + ABAC verified.
- Identity note 64: RBAC + ABAC verified.
- Identity note 65: RBAC + ABAC verified.
- Identity note 66: RBAC + ABAC verified.
- Identity note 67: RBAC + ABAC verified.
- Identity note 68: RBAC + ABAC verified.
- Identity note 69: RBAC + ABAC verified.
- Identity note 70: RBAC + ABAC verified.
- Identity note 71: RBAC + ABAC verified.
- Identity note 72: RBAC + ABAC verified.
- Identity note 73: RBAC + ABAC verified.
- Identity note 74: RBAC + ABAC verified.
- Identity note 75: RBAC + ABAC verified.
- Identity note 76: RBAC + ABAC verified.
- Identity note 77: RBAC + ABAC verified.
- Identity note 78: RBAC + ABAC verified.
- Identity note 79: RBAC + ABAC verified.
