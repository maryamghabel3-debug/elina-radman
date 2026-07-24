# Data Protection and Encryption - ElinaOS

Protects data at rest, in transit, and in use across ElinaOS pipeline.

## Classification

| Level | Examples | Encryption | Retention |
|---|---|---|---|
| PUBLIC | docs, dashboard.html | TLS | indefinite |
| INTERNAL | content/queue JSON | AES-256 at rest | 90d |
| CONFIDENTIAL | Telegram user_id hash | AES-256-GCM + vault | 30d |
| RESTRICTED | GitHub PAT, Gemini key | vault, HSM if possible | 90d rotation |

## At Rest
- Files in `content/` encrypted if marked confidential.
- TARGET: `content/memory_store.json` uses envelope encryption: DEK per file,
  TARGET: KEK in vault, KMS rotation every 90 days.
- Images in `images/` not encrypted (public), but metadata stripped.
- TARGET: Mobile local DB: SQLCipher, key in Keystore/Keychain.
- Backup: encrypted tar.gz with age or GPG, stored offsite.

## In Transit
- TARGET: TLS 1.3 only, cipher TLS_AES_128_GCM_SHA256, TLS_AES_256_GCM_SHA384.
- TARGET: HSTS max-age 31536000, includeSubDomains, preload.
- TARGET: Certificate pinning for GitHub API and Gemini API.
- No http:// fallback, all redirects to https:// with 301.
- TARGET: mTLS for agent-to-agent calls inside VPC.

## In Use
- Secrets loaded into memory only when needed, zeroed after use.
- LLM prompts do not include RESTRICTED data unless required + logged.
- PII redaction via regex + NER before logging and before LLM.
- Data masking: show only last 4 chars of tokens in UI.

## Key Derivation
- TARGET: Passwords: Argon2id, m=64MB, t=3, p=2, salt 16 bytes.
- TARGET: Deterministic IDs: HMAC-SHA256 with pepper from vault.
- Token generation: `secrets.token_urlsafe(32)`, 256-bit entropy.

## Vault Usage
- TARGET: Vault path: `secret/elina/*`, policies per agent role.
- TARGET: No vault token in code, injected via env at runtime.
- Lease TTL 1h, max 24h, renew via sidecar.
- TARGET: Audit: every vault read logged with requester and justification.

## DLP Rules
- Block upload of files containing `BEGIN PRIVATE KEY` or AWS key pattern.
- Block egress of CONFIDENTIAL data to non-allowlisted domains.
- Alert on bulk read: >100 files in 1 minute.
- TARGET: Quarantine content queue items with suspected PII over threshold.

## Secure Erase
- File delete: overwrite 3x with random + zero, then unlink.
- Memory: `memset_s` equivalent via `ctypes` zero after secret use.
- DB purge: VACUUM after DELETE to remove free pages.

## Compliance
- NIST 800-53 SC-28, SC-12, SC-13, AC-3.
- GDPR Art 32: encryption, pseudonymization, breach notification.
- Data residency: default EU (Amsterdam), configurable.

## Testing
- TARGET: Automated test: check TLS config via `testssl.sh`.
- At-rest check: list unencrypted files in confidential paths.
- Restore test: monthly backup restore drill.
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
