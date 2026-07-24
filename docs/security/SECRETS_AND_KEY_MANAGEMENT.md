# Secrets and Key Management - ElinaOS

Manages API keys, PATs, tokens, encryption keys with rotation and auditing.

## Secret Inventory

| Secret | Storage | Rotation | Scope | Used By |
|---|---|---|---|---|
| GitHub PAT | vault secret/elina/github_pat | 90d | repo write | github_manager |
| Gemini API Key | vault secret/elina/gemini | 90d | llm | llm_router |
| Telegram Bot Token | vault secret/elina/telegram_bot | 90d | bot | elina_bot.py |
| JWT Signing Key | vault transit or JWKS | 30d | auth | dashboard, agents |
| AES KEK | vault transit | 90d | encryption | content store |
| Age/GPG backup key | offline vault | 365d | backup | backup job |

## Storage Rules - Never Do
- Never store secret in git, docs, issues, PRs, logs, or images metadata.
- Never log secret value, only last 4 chars + hash for audit.
- Never pass secret as command line arg, only env or file descriptor.
- Never echo secret in GitHub Actions log, use mask.
- Secret in code fails CI secret scan and blocks merge.

## Storage Rules - Do
- TARGET: Store in vault `secret/elina/*` with policy per role.
- Inject via env var at runtime, or via file mounted tmpfs.
- Load lazily, keep in memory minimal time, zero after use.
- TARGET: Use vault dynamic secrets if possible: short-lived GitHub token.
- TARGET: Backup vault seal keys via Shamir split among 3 operators.

## Rotation Procedure
1. Generate new secret in provider (GitHub, Gemini, Telegram).
TARGET: 2. Write new version to vault: `vault kv put secret/elina/key value=new`.
3. Update dependent services to reload via SIGHUP or restart.
4. Verify new secret works via `scripts/test_media.py` etc.
5. Revoke old secret after 24h grace period.
6. Audit log entry: who rotated, when, reason.
7. If automatic rotation fails, alert SEV2.

## Access Control
- TARGET: Vault policy: `read:secret/elina/github_pat` only for github_manager.
- TARGET: Policy file: `vault/policies/github-manager.hcl` versioned.
- No root token used in daily ops, only break-glass.
- Break-glass token TTL 1h, requires 2 operators to unseal and logs SEV1.

## GitHub Actions Secrets
- Repository secrets: GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, GH_PAT.
- Environment secrets for prod only, not for PRs from forks.
- Actions workflow masks secrets via `::add-mask::`.
- No `pull_request_target` with untrusted code accessing secrets.
- Dependabot PRs cannot access secrets (default).

## Client-Side Secrets (Mobile)
- Mobile app does not contain static API keys, uses backend.
- TARGET: Backend issues short-lived JWT after device attestation.
- TARGET: Storage on device: Android Keystore, iOS Keychain, not SharedPrefs.
- If device rooted/jailbroken, limit to read-only + warn user.

## Encryption Keys
- TARGET: KEK in vault transit engine, DEK per file random 256-bit.
- Envelope: DEK encrypted by KEK, stored alongside file metadata.
- DEK zeroed after use, KEK never exported.
- KEK rotation: re-wrap DEKs without re-encrypting files.

## Detection - Secret Scan
- TARGET: Pre-commit hook: `gitleaks` + `detect-secrets`.
- TARGET: CI: `trufflehog git file://. --fail`.
- TARGET: Allowlist file `.gitleaksignore` for example keys in docs (documented as EXAMPLE).
- If real secret detected -> DENY push, SEV1, immediate revoke.
- Example allowlist entry: `EXAMPLE_GH_PAT=ghp_EXAMPLE123` marked as test data.

## Audit
- TARGET: Every vault read/write logged with: actor, path, time, jti, IP hash.
- Logs shipped to `secret.access` category, 365d retention.
- Monthly review of who accessed what, anomalies flagged.

## Incident - Secret Leak
- Follow INCIDENT_RESPONSE.md Playbook A.
- Revoke immediately, do not attempt to purge git history first (revoke first).
- TARGET: Search git history with `git log -p -S <fragment>` or trufflehog.
- If leak public, purge history via BFG after revoke and force push with care.

## Compliance
- OWASP ASVS 2.10, 6.4 secret management.
- NIST 800-53 SC-12, IA-5 authenticator management.
- SOC2 CC6.1 logical access control.

## Future
- TARGET: Migrate to HSM for KEK if scale grows.
- TARGET: Use SPIRE for workload identity instead of static PAT.
- TARGET: Automated rotation via vault dynamic secrets engine for GitHub.
