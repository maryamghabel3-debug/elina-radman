# Security Architecture - ElinaOS - Zero-Trust Deep Dive

This doc expands zero-trust across 7 pillars: identity, device, network,
app, data, visibility, automation.

## Overview
- ElinaOS is Persian-first multimodal AI workspace, not just content.
- Factory architecture: 20+ agents cooperating via message bus.
- Threat surface: Telegram bot, web dashboard, mobile app, GitHub Actions,
  LLM providers, image/video gen, file system, memory store.
- Security goal: confidentiality, integrity, availability + content trust.

## Pillars

### 1. Identity - Never Trust, Always Verify
- TARGET: Humans: GitHub OAuth + MFA, short-lived PAT, GPG signed commits.
- TARGET: Agents: SPIFFE IDs, JWT SVID 5m TTL, attestation via parent process.
- TARGET: Workloads: GitHub Actions OIDC token, aud = elina-aud, exp 10m.
- TARGET: Devices: AppCheck + device attestation, device ID bound to JWT.
- Every request has identity, verified at each hop, not just edge.

### 2. Device - Healthy Device Required
- TARGET: Dashboard device posture: check OS version, browser, MFA present.
- Mobile: SafetyNet / Play Integrity, jailbreak detection.
- TARGET: Agents: runner image pinned SHA, SBOM generated, vuln scanned.
- If device unhealthy, step-up auth or deny access to RESTRICTED.
- Device inventory in `docs/CONNECTION-GUIDE.md`, updated quarterly.

### 3. Network - Micro-Segmentation
- VPC: public subnet for web/dashboard, private for workers and agents.
- Security groups: dashboard can talk to API only via 443, not DB directly.
- TARGET: Agents egress: NetworkGuard allowlist, default DENY, DNS pinning.
- No lateral movement: agent A cannot call agent B unless policy allows.
- TARGET: Service mesh: mTLS between internal services, cert rotation weekly.
- No ingress to workers, only queue pull model.
- Private IP ranges blocked for external fetch: 10/8, 172.16/12, 192.168/16,
  169.254/16, 127/8.
- TARGET: WAF in front of dashboard: OWASP Top10 rules, rate limit 60/min/IP.

### 4. Application - Secure SDLC
- TARGET: SAST: Semgrep rules for eval, pickle, hardcoded secret, traversal.
- TARGET: DAST: ZAP scan weekly against dashboard staging.
- Dependency: Dependabot + pip-audit, CVSS>7 blocks merge.
- TARGET: Secrets scan: gitleaks pre-commit + trufflehog CI.
- License scan: no GPL in prod image.
- Code review: 2 approvals required for security files, 1 for others.
- TARGET: Branch protection: require status checks, dismiss stale review.
- Signed commits: GPG required for main pushes? Warn if not.
- Build: hermetic, pinned base images SHA, no latest tag.
- App container runs as non-root, read-only FS, no cap add.
- Seccomp profile, drop all caps.

### 5. Data - Classification and Protection (see DATA_PROTECTION)
- Public, Internal, Confidential, Restricted as per DATA_PROTECTION.md.
- TARGET: Encryption at rest AES-256-GCM, envelope with KEK in vault.
- TARGET: In transit TLS 1.3 only, mTLS for internal, cert pinning for external.
- Backup encrypted with age, offsite, restore test monthly.
- DLP: block private key, AWS key patterns on egress.
- TARGET: PII pseudonymized via HMAC with pepper from vault.

### 6. Visibility - Logging and Monitoring (see LOGGING_AND_MONITORING)
- All guard decisions, auth, tool invokes, publish events logged.
- TARGET: Logs append-only, hash chain, tamper detection hourly.
- TARGET: SIEM rules: injection spike, brute force, exfil, secret anomaly.
- Alerts via Telegram admin + GitHub Issue + dashboard banner.
- Metrics: guard rate, auth failure, latency, cost, publish rate.
- Forensics: timeline export script, correlated by JTI.
- Dashboard in `dashboard/app.py` shows health and alerts.

### 7. Automation and Orchestration - Secure Automation
- GitHub Actions workflows in `.github/workflows/` pinned to SHA.
- Workflow permissions: `permissions: contents: read` minimal, not write all.
- No `pull_request_target` with secrets on untrusted code.
- Bot runner workflow: `bot-runner.yml` runs on schedule, short-lived token.
- Daily content workflow: `daily-content.yml` isolated, no secret for PRs.
- TARGET: Build-android workflow: `build-android.yml` signs via vault, not hardcoded.
- Image/video test workflows: `test-image.yml`, `test-video.yml`.
- Diagnose Gemini workflow: `diagnose-gemini.yml` no secrets in logs.
- Issue-driven update workflow: `issue-driven-update.yml` validates issue body.
- Post-content workflow: `post-content.yml` confirmation required.
- Runner: ephemeral, clean after each job, no persistent creds.

## Trust Boundaries Diagram (Logical)

```
TARGET: Internet -> WAF -> [Web/Mobile/Telegram Channel Guards] -> API Gateway
TARGET: API Gateway -> [Identity - OPA Policy] -> [Agent Runtime Guardrails]
TARGET: Guardrails -> [Tool Allowlist + Schema] -> [NetworkGuard Egress]
Egress -> [Allowlist: github, gemini, telegram] -> External
Internal: Agents isolated via message bus, not direct call,
  TARGET: MemoryGuard per tenant, Logging to append-only store,
  TARGET: Secrets via vault, not env in code,
  Publish via confirmation + human approval for high-risk,
  TARGET: GitHub push via scoped PAT, MFA enforced,
```

## Data Flow (Example: Telegram -> Publish)
TARGET: 1. Telegram user sends /generate: bot webhook receives, validates token.
TARGET: 2. Channel guard rate limit + BIDI + injection marker check.
3. Bot emits `content/queue/202607...json` with hashed user_id.
TARGET: 4. Worker pulls queue, InputGuard sanitizes, LLM generates.
TARGET: 5. OutputGuard scans for PII/secrets/exfil, redacts if needed.
6. Publisher agent checks policy: publish intent requires confirmation.
7. Dashboard shows pending approval with diff.
TARGET: 8. Operator approves via MFA, publisher calls platform_managers.
TARGET: 9. NetworkGuard checks egress allowlist for platform API.
10. Publish event logged with hash of content, not full PII.
TARGET: 11. SIEM correlates and updates metrics.

## Controls Mapping to Layers

| Layer | Controls | Docs |
|---|---|---|
| Edge | WAF, rate limit, Bot token rotation | CHANNEL_SECURITY |
| Identity | OPA, RBAC/ABAC, MFA | IDENTITY_ACCESS |
| Runtime | 5 guardrails, 8 actions, fail-closed | SECURITY_AGENT_RUNTIME |
| Data | classification, encryption, DLP | DATA_PROTECTION |
| Secrets | vault, rotation, no hardcode | SECRETS_MANAGEMENT |
| Monitoring | SIEM rules, hash chain logs | LOGGING_MONITORING |
| Testing | SAST/DAST, injection tests | SECURITY_TESTING |
| Supply Chain | third-party review, SBOM | THIRD_PARTY |
| Incident | playbooks, MTTR | INCIDENT_RESPONSE |
| Prompt | 8-layer injection defense | PROMPT_INJECTION |
| Agent | trust levels L0-L3, least privilege | AGENT_SECURITY_MODEL |

## Threats Addressed
- TARGET: Prompt injection -> 8-layer defense.
- Agent hijack -> runtime guardrails + network isolation.
- TARGET: Secret leak -> vault + rotation + scan.
- Supply chain -> third party review + pinned actions.
- Data exfil -> DLP + egress allowlist + output guard.
- TARGET: Abuse -> rate limit + SIEM + channel isolation.
- TARGET: Memory leak -> MemoryGuard + tenant isolation.
- TARGET: Privilege escalation -> RBAC/ABAC + OPA + no wildcard.

## Compliance
- NIST 800-207 Zero Trust: identity, device, network, app, data, vis, auto.
- NIST AI RMF: Map, Measure, Manage, Govern for AI risks.
- OWASP LLM Top 10 + ASVS 5.0 + MLSecOps Top 10.
- SOC2 CC6, CC7, CC8: logical access, monitoring, change mgmt.
- GDPR: minimization, encryption, retention, breach notification.

## Security Dependencies
- TARGET: vault: secret storage, transit encryption.
- TARGET: OPA: policy engine.
- TARGET: Semgrep: SAST.
- TARGET: gitleaks/trufflehog: secret scan.
- TARGET: GitHub OIDC: workload identity.
- Streamlit: dashboard, hardened config.
- Kivy: mobile, permissions minimal.

## Deployment Security
- Infra as Code: Terraform with tfsec and checkov.
- TARGET: Secrets via vault, not Terraform state plain.
- Blue-green deploy, canary 10%, auto rollback on error >1%.
- Immutable image: tag = git SHA, not latest.
- Runtime: read-only FS, non-root, seccomp, no cap.

## Future
- eBPF network visibility for agent egress.
- Confidential computing for LLM inference.
- Post-quantum crypto for KEK (hybrid X25519+Kyber).
- TARGET: Formal verification of OPA policies.
- Continuous red team automation.

## Checklist for New Feature
- [ ] Data classification assigned?
- TARGET: [ ] Identity and scope defined in OPA?
- [ ] Input validation + sanitization + test?
- [ ] Output filtering + DLP added?
- TARGET: [ ] Secrets via vault, not hardcoded?
- [ ] Logging added for guard decisions?
- TARGET: [ ] Rate limit defined?
- [ ] Threat model updated?
- [ ] Security tests added?
- [ ] Docs updated in docs/security/?
- [ ] PR has 2 reviewers if security file?
- TARGET: [ ] SAST/secret scan PASS?
