# Logging and Monitoring - ElinaOS

Security observability: detect injection, abuse, and exfil early.

## Log Categories

| Category | Source | Retention | Sensitivity |
|---|---|---|---|
| guard.decision | runtime guardrails | 90d | internal |
| auth.event | identity layer | 90d | confidential |
| tool.invoke | agent tool calls | 30d | internal |
| channel.event | Telegram/web/mobile | 30d | internal |
| publish.event | publisher agents | 90d | public + hash |
| secret.access | vault | 365d | restricted |

## Log Schema (JSON)
```json
{
  "ts": "2026-07-24T02:30:00Z",
  "tenant": "hash",
  "agent": "prompt_engineer",
  "event": "guard.decision",
  "guard": "InputGuard",
  "action": "QUARANTINE",
  "reason": "bidi_override_detected",
  "latency_ms": 12,
  "jti": "...",
  "cost": 0.02
}
```

## What to Log, What Not
- Log: guard decisions, auth success/failure, tool calls, publish attempts.
- Don't log: secrets, PII raw, Telegram message full content, private keys.
- PII redacted: replace email with `u***@example.com`, IP with hash.
- Sampling: high-volume web events sampled 10% after 1k/min.

## Monitoring Rules (SIEM)

1. **Injection Spike**: >10 QUARANTINE in 5m -> SEV2 alert.
2. **Brute Force**: >5 auth failures same user in 10m -> block + alert.
3. **Exfil Attempt**: OutputGuard DENY with URL exfil pattern -> SEV1.
4. **Secret Access Anomaly**: vault read outside business hours -> SEV2.
5. **Publish Anomaly**: >20 publishes in 1h -> SEV3.
6. **Tool Abuse**: same tool >100 calls in 10m -> rate limit + alert.
7. **Cost Spike**: session cost >$1 -> alert + kill.
8. **Log Tamper**: hash chain break -> SEV1.

## Alerting Channels
- Telegram: private admin channel via bot with alert role.
- GitHub Issue: auto-create issue with label `security-alert`.
- Email: security owner, if configured via vault.
- Dashboard banner: shows active alerts in `dashboard/app.py`.

## Metrics Dashboards
- Guard action rate per minute, per guard.
- Auth failure rate, success rate.
- Tool call latency p50/p95.
- Publish success/failure rate.
- Vault access rate.
- Cost per agent per day.

## Storage and Integrity
- Logs append-only, object storage with versioning, no delete.
- Hash chain: each log entry includes prev hash, verified hourly.
- Backup: daily snapshot to second region, encrypted.
- Access: only auditor role, MFA required.

## Retention and Purge
- 30d hot, 90d warm (S3), 365d cold for restricted logs.
- Purge job: hard delete after retention + double confirmation.
- Purge logs with record of what was purged, when, who approved.

## Forensics
- Timeline export: `python scripts/security_logs.py --since 24h`.
- Correlation: join guard + auth + tool logs by JTI or session ID.
- Redaction audit: ensure no PII leaked in exported timeline.

## Compliance
- SOC2 CC7.2, CC6.1: system monitoring and audit log.
- GDPR: logs contain only pseudonymized data.
- CIS 8.2: central log collection.

## Runbooks
- If alert fires, jump to INCIDENT_RESPONSE.md Playbook B or A.
- False positive: tune rule threshold via PR, need 2 approvals.
- Monitoring note 86: SIEM rule tuned.
- Monitoring note 87: SIEM rule tuned.
- Monitoring note 88: SIEM rule tuned.
- Monitoring note 89: SIEM rule tuned.
