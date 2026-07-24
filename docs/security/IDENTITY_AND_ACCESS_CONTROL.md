# Identity and Access Control - ElinaOS

Identity-first zero-trust: every request authenticated, authorized, audited.

## Principal Types
- TARGET: Human operator: GitHub account + MFA + GPG signed commits.
- TARGET: Agent identity: SPIFFE ID `spiffe://elina/agent/<name>`, JWT SVID.
- Workload: GitHub Actions runner, token with audience `elina-aud`.
- Device: mobile app instance, device ID + app attestation.

## Authentication
- Human: GitHub OAuth, PAT with fine-grained scopes, expiry 90d.
- TARGET: Agent: JWT 5m TTL, signed by issuer `elina-issuer`, kid rotation.
- TARGET: Workload: OIDC token from GitHub Actions, aud verified.
- Device: Firebase App Check or Apple DeviceCheck.
- Passwords: not used, only tokens and keys.

## Authorization Models
- TARGET: RBAC: roles operator, publisher, viewer, auditor.
- TARGET: ABAC: attributes tenant, channel, data_class, risk_score.
- TARGET: Policy engine: OPA Rego, policy files in `docs/security/policies/`.
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
- TARGET: JWT expiry 15m, refresh token 24h, rotation on each refresh.
- Refresh token bound to device fingerprint hash.
- Logout revokes refresh token via denylist in Redis (TTL 24h).
- Concurrent session limit: 3 per user, oldest kicked.

## MFA and Step-up
- TOTP or WebAuthn required for admin actions.
- Step-up auth if risk score high: new IP, impossible travel.
- Risk score from: IP reputation, device, behavior baseline.

## Audit
- Every auth decision logged: who, what, when, result, reason.
- TARGET: Failed logins count towards rate limit and alert after 5.
- Logs include JTI to trace token lifecycle.

## Secrets
- TARGET: No secret in JWT payload, only sub, scope, exp, jti.
- TARGET: Private keys stored in vault, public keys in JWKS endpoint.
- JWKS rotation weekly, cache 1h max.

## Hardening
- No wildcard `*` allowed in policies.
- TARGET: Policy changes require PR + 2 reviewers + CI OPA test.
- Break-glass account exists but monitored and expires in 1h.
- TARGET: Additional V2 control 1 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 2 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 3 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 4 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 5 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 6 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 7 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 8 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 9 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 10 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 11 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 12 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 13 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 14 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 15 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 16 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 17 to be defined - requires owner review before implementation.
