# Security Agent Runtime Policy - ElinaOS

Runtime isolates untrusted LLM output from privileged actions.
Every tool call passes through 5 guardrails before execution.

## 5 Guardrails

TARGET: 1. **InputGuard**: validates prompt length, charset, BIDI, injection markers.
TARGET: 2. **ToolGuard**: checks tool allowlist, args schema, rate limit, cost cap.
TARGET: 3. **OutputGuard**: filters PII, secrets, disallowed content, exfil URLs.
TARGET: 4. **MemoryGuard**: scopes memory per agent, prevents cross-tenant leak.
TARGET: 5. **NetworkGuard**: egress allowlist, no private IP, DNS pinning.

## Trust Levels
- L0 Untrusted: external user input, web scraping.
- L1 Semi-trusted: curated tools, internal APIs.
- L2 Trusted: system prompts, signed policies.
- L3 Privileged: key management, deployment, only human operator.

## 8 Protective Actions

| # | Action | Trigger | Example |
|---|---|---|---|
| 1 | ALLOW | clean + allowlisted | read docs file |
| 2 | SANITIZE | suspicious but fixable | strip HTML tags |
| 3 | REDACT | PII/secret detected | mask API key |
| 4 | RATE_LIMIT | too many tool calls | 429 + backoff |
| 5 | CHALLENGE | ambiguous intent | ask for confirmation |
| 6 | QUARANTINE | injection marker | isolate to review queue |
| 7 | DENY | policy violation | block file write outside |
| 8 | ALERT + KILL | critical exfil attempt | terminate session |

## Execution Flow
TARGET: User Input -> InputGuard -> LLM -> OutputGuard -> ToolGuard ->
TARGET: MemoryGuard -> NetworkGuard -> Tool Execution -> Log.
On failure, fallback to safe state and emit audit event.

## Memory Isolation
- Per-agent vector store, tenant ID in every key.
- No global memory write without L2 approval.
- TTL 24h for episodic, 90d for semantic with review.
- TARGET: Embedding encryption at rest using AES-256-GCM.

## Tool Policy Example (YAML)
```yaml
tools:
  - name: publish_content
    allowed_for: [publisher, content_creator]
    max_calls_per_min: 5
    args_schema: {platform: enum, content_id: string}
    requires_confirmation: true
    egress: []
```

## Resource Limits
- Max tokens per turn: 4000, max turns: 20.
- Max file writes per session: 50, max size 2MB.
- Max outbound requests: 30 per hour to allowlisted domains.
- Cost cap: $0.50 per session, abort if exceeded.

## Logging
- Every guard decision logged with: guard, action, reason, latency.
- Logs shipped to append-only store, tamper-evident hash chain.
- PII redacted before storage.

## Testing
- Unit tests for each guard with adversarial inputs.
- Chaos test: random injection markers in 10% of prompts.
- Red team: simulate agent hijack, test DENY/ALERT path.

## Fail-Closed Design
- If guard crashes, default DENY.
- If policy file invalid, default DENY all tools.
- If network guard cannot resolve allowlist, block egress.

## Operator Override
- TARGET: Human in loop can approve QUARANTINE items via dashboard.
- TARGET: Override requires MFA + second approver for L3 actions.
- All overrides audited with justification ticket ID.

## Version History
- v1.1: Added 5 guardrails, 8 actions, fail-closed logic.
- v1.2: Added cost caps and BIDI checks.
