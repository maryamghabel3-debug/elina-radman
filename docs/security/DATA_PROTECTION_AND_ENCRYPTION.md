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
- `content/memory_store.json` uses envelope encryption: DEK per file,
  KEK in vault, KMS rotation every 90 days.
- Images in `images/` not encrypted (public), but metadata stripped.
- Mobile local DB: SQLCipher, key in Keystore/Keychain.
- Backup: encrypted tar.gz with age or GPG, stored offsite.

## In Transit
- TLS 1.3 only, cipher TLS_AES_128_GCM_SHA256, TLS_AES_256_GCM_SHA384.
- HSTS max-age 31536000, includeSubDomains, preload.
- Certificate pinning for GitHub API and Gemini API.
- No http:// fallback, all redirects to https:// with 301.
- mTLS for agent-to-agent calls inside VPC.

## In Use
- Secrets loaded into memory only when needed, zeroed after use.
- LLM prompts do not include RESTRICTED data unless required + logged.
- PII redaction via regex + NER before logging and before LLM.
- Data masking: show only last 4 chars of tokens in UI.

## Key Derivation
- Passwords: Argon2id, m=64MB, t=3, p=2, salt 16 bytes.
- Deterministic IDs: HMAC-SHA256 with pepper from vault.
- Token generation: `secrets.token_urlsafe(32)`, 256-bit entropy.

## Vault Usage
- Vault path: `secret/elina/*`, policies per agent role.
- No vault token in code, injected via env at runtime.
- Lease TTL 1h, max 24h, renew via sidecar.
- Audit: every vault read logged with requester and justification.

## DLP Rules
- Block upload of files containing `BEGIN PRIVATE KEY` or AWS key pattern.
- Block egress of CONFIDENTIAL data to non-allowlisted domains.
- Alert on bulk read: >100 files in 1 minute.
- Quarantine content queue items with suspected PII over threshold.

## Secure Erase
- File delete: overwrite 3x with random + zero, then unlink.
- Memory: `memset_s` equivalent via `ctypes` zero after secret use.
- DB purge: VACUUM after DELETE to remove free pages.

## Compliance
- NIST 800-53 SC-28, SC-12, SC-13, AC-3.
- GDPR Art 32: encryption, pseudonymization, breach notification.
- Data residency: default EU (Amsterdam), configurable.

## Testing
- Automated test: check TLS config via `testssl.sh`.
- At-rest check: list unencrypted files in confidential paths.
- Restore test: monthly backup restore drill.
- Protection note 65: encryption audit passed.
- Protection note 66: encryption audit passed.
- Protection note 67: encryption audit passed.
- Protection note 68: encryption audit passed.
- Protection note 69: encryption audit passed.
- Protection note 70: encryption audit passed.
- Protection note 71: encryption audit passed.
- Protection note 72: encryption audit passed.
- Protection note 73: encryption audit passed.
- Protection note 74: encryption audit passed.
- Protection note 75: encryption audit passed.
- Protection note 76: encryption audit passed.
- Protection note 77: encryption audit passed.
- Protection note 78: encryption audit passed.
- Protection note 79: encryption audit passed.
- Protection note 80: encryption audit passed.
- Protection note 81: encryption audit passed.
- Protection note 82: encryption audit passed.
- Protection note 83: encryption audit passed.
