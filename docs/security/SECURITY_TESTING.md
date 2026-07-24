# Security Testing - ElinaOS

Testing ensures controls work and stay working. Shift left and continuous.

## Test Pyramid for Security

```
Unit (guard logic, validators)
Integration (agent + guard + tool)
E2E (Telegram -> queue -> publish with injection)
Manual (red team, pen test)
Prod (SIEM, bug bounty light)
```

## Unit Tests
- InputGuard: BIDI, zero-width, injection markers, length, charset.
- ToolGuard: allowlist, schema, rate limit, cost cap.
- OutputGuard: PII, secret patterns, exfil URL, instruction leak.
- MemoryGuard: tenant isolation, cross-tenant read blocked.
- NetworkGuard: private IP block, allowlist, DNS pinning.
- Location: `tests/test_agents.py` and `scripts/test_*.py`.
- Each test includes adversarial cases + benign Persian/English.

## Injection Tests (100+ cases)
- Direct: `ignore previous instructions` + variants.
- Indirect: payload hidden in fake webpage or doc metadata.
- Encoding: base64, hex, ROT13, zero-width joiner.
- BIDI: RTL override `\u202e` hides malicious.
- Tool output: malicious API returns instruction.
- Memory: poisoned memory entry tries to hijack next turn.
- Multi-turn: gradually steer agent.
- Stored in `tests/test_agents.py` as constants.
- Must PASS: no bypass, 0% false negative on injection set.
- False positive <2% on benign dataset `content/trend_visuals.json`.

## SAST (Static)
- Tool: Semgrep with rules: `no-eval`, `no-pickle-unsafe`,
  `no-hardcoded-secret`, `no-path-traversal`, `no-sql-injection`.
- CI workflow: `.github/workflows/tests.yml` runs semgrep.
- Fail if high severity finding.
- SARIF uploaded to GitHub Security tab.

## DAST (Dynamic)
- Tool: OWASP ZAP baseline against dashboard staging.
- Weekly run via `scripts/test_media.py` with ZAP proxy.
- No high risk findings allowed in main.
- Rate limit test: try 100 req in 1m, expect 429 after 60.
- Auth bypass test: try access admin without token, expect 403.

## Secret Scan
- Pre-commit: `gitleaks protect --staged`.
- CI: `trufflehog git file://. --fail --only-verified`.
- If secret found -> block PR, SEV1 alert.
- Allowlist: example keys marked `EXAMPLE` in docs.

## Dependency Scan
- Dependabot enabled for pip, GitHub Actions.
- `pip-audit` in CI, fail if CVSS>7 without fix.
- `npm audit` for dashboard if JS added.
- SBOM generated via `syft` on image build.

## Container Scan
- Trivy scan on app image.
- No CRITICAL vuln allowed in main.
- Base image pinned SHA, not latest.
- Image runs as non-root, read-only FS validated.

## Mobile Scan (Buildozer)
- Check permissions in `app/buildozer.spec`, no extra perms.
- Scan APK with `mobsfscan` light.
- No hardcoded secret in APK resources.

## E2E Security Scenarios
- Scenario 1: Telegram user tries injection to publish spam -> blocked.
- Scenario 2: Web user tries traversal `../../etc/passwd` -> blocked.
- Scenario 3: Agent tries egress to private IP -> NetworkGuard DENY.
- Scenario 4: Content queue with PII -> OutputGuard redacts + logs.
- Each scenario automated in `scripts/test_live_image.py` etc.

## Performance Security
- Load test: 100 concurrent users, guard latency p95 <100ms.
- Cost test: session that exceeds $0.50 aborted.
