# Incident Response Plan - ElinaOS

Preparation for security incidents with playbooks and timelines.

## Severity Levels

| Level | Impact | Example | Response SLO |
|---|---|---|---|
| SEV1 | Critical | secret leak, RCE | 15m ack, 1h contain |
| SEV2 | High | prompt injection -> exfil | 30m ack, 4h contain |
| SEV3 | Medium | spam publish via bot | 4h ack, 24h fix |
| SEV4 | Low | dependency vuln low | 24h ack, 72h fix |

## Roles
- Incident Commander (IC): owner GitHub account, drives response.
- Comms: updates stakeholders and status page.
- Security Engineer: investigates, contains, eradicates.
- Scribe: documents timeline, actions, decisions.

## Detection Sources
- Guard alerts: DENY, ALERT+KILL actions from runtime guardrails.
- TARGET: Monitoring: SIEM alert on 5+ DENY in 10m, or egress to disallowed.
- User report: GitHub issue with label `security` + email.
- Dependency scan: Dependabot PR with CVSS >7 triggers SEV3.

## Playbooks

### Playbook A: Secret Leak
TARGET: 1. Revoke secret in vault and GitHub/emprovider immediately.
2. Rotate all derived tokens and DEKs.
TARGET: 3. Search GitHub history with trufflehog, purge if needed.
4. Force re-auth all sessions.
5. Post-mortem: how leaked, add detection.

### Playbook B: Prompt Injection -> Tool Abuse
TARGET: 1. Quarantine session, kill agent process.
2. Review `content/queue` for malicious items, delete.
3. Block user and IP hash at channel guard.
TARGET: 4. Update prompt injection markers in `PROMPT_INJECTION_DEFENSE.md`.
5. Add unit test replicating injection payload.

### Playbook C: Unauthorized Publish
1. Unpublish content via platform manager with audit log.
2. Disable publisher tool via policy flip.
3. Notify operator with diff of published content.
TARGET: 4. Require MFA re-auth before re-enable publish.

## Containment
- TARGET: Isolate affected agent by revoking its JWT.
- Disable GitHub Action workflow `bot-runner.yml` if compromised.
- TARGET: Block egress at NetworkGuard level.
- Snapshot logs for forensics before purge.

## Eradication and Recovery
- Patch code, add guard, test with adversarial cases.
- Restore from last known good backup if data tampered.
- Gradual re-enable: canary 10% traffic, monitor 24h.

## Post-Mortem Template
- Summary, timeline (UTC), impact, root cause, detection gap,
  remediation, preventive actions, owners, tickets.
- Post-mortem within 5 days for SEV1/2, 10 days for SEV3.

## Communication
- Internal: GitHub issue with label `incident` + private note.
- External users: if PII impacted, notify within 72h per GDPR.
- Status page: dashboard banner + Telegram announcement.

## Drills
- Quarterly tabletop exercise, simulate injection + secret leak.
- Annual red team exercise with external reviewer.
- Drill metrics: MTTD, MTTR, time to contain.

## Tooling
- Logs in `dashboard/app.py` with incident view.
- Forensics: `scripts/security_logs.py` to export timeline.
- Isolation: `scripts/disable_agent.py --agent publisher`.
- TARGET: Additional V2 control 1 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 2 to be defined - requires owner review before implementation.
- TARGET: Additional V2 control 3 to be defined - requires owner review before implementation.
