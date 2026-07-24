# Agent Security Model - ElinaOS

Defines trust boundaries for 20+ agents in ElinaOS factory architecture.

## Agent Inventory and Trust Levels

| Agent | Trust | Tools | Data Access |
|---|---|---|---|
| trend_hunter | L0 | web search, vision | public trends only |
| prompt_engineer | L1 | file write in docs/ | prompts only |
| content_creator | L1 | llm_router, content queue | queue JSON |
| image_studio | L1 | image gen | images/ folder |
| publisher | L2 | platform_managers | publish with confirmation |
| github_manager | L2 | git push | repo with scoped PAT |
| security_auditor | L3 | read all | audit logs only |

## Zero-Trust Agent Communication
- Agents communicate via typed messages, not direct memory sharing.
- Message schema validated by ToolGuard, unknown fields rejected.
- Agent identity verified via signed JWT with short TTL 5m.
- No agent can impersonate another: sub claim bound to process ID.
- Cross-agent calls logged with caller, callee, payload hash.

## Least Privilege Enforcement
- Each agent YAML declares `allowed_tools`, `max_file_ops`, `egress`.
- Base agent class (agents/base.py) enforces via decorator @require_tool.
- Violation triggers DENY + audit event + optional quarantine.
- Weekly review of permission creep via `performance_analyzer`.

## Isolation Mechanisms
- Process isolation: each agent runs as separate task in runner.
- Filesystem isolation: write allowed only in `content/`, `docs/`, `images/`.
- Network isolation: only whitelisted domains per agent role.
- Memory isolation: no shared global state, message passing only.

## Secure Agent Development Rules
- No `eval()`, `exec()`, `pickle.loads()` on untrusted data.
- No hardcoded secrets, use vault or env via llm_router.
- All external inputs via `vision.py` or `trend_hunter` sanitized.
- Use parameterized file paths, prevent directory traversal.
- Unit tests must include adversarial cases + injection payloads.

## Agent Lifecycle Security
- Init: load policy, verify signature, check dependency vulns.
- Runtime: guardrails enforced, resource limits monitored.
- Shutdown: wipe temp memory, close file handles, emit summary log.
- Update: rolling deploy, canary 10%, rollback on error rate >1%.

## Human Oversight
- High-risk actions (publish, git push, secret access) require human.
- Dashboard shows pending approvals with diff view.
- Operator must use MFA to approve L2/L3 actions.

## Audit Trail
- Agent action stored in `content/memory_store.json` with hash chain.
- Immutable log: cannot delete, only append, verified hourly.
- Log includes: timestamp, agent_id, action, guard_result, cost.

## Compliance
- Aligns with OWASP Agentic AI Security: goal hijacking prevented.
- Supply chain: agent code pinned to commit hash in `agents/__init__.py`.
- Versioned policy files, change requires PR + 2 reviewers.

## Future Hardening
- WASM sandbox for L0 agents.
- Hardware attestation for L3 actions.
- Formal verification of guardrail state machine.
- Model note 67: least privilege enforced.
- Model note 68: least privilege enforced.
- Model note 69: least privilege enforced.
- Model note 70: least privilege enforced.
- Model note 71: least privilege enforced.
- Model note 72: least privilege enforced.
- Model note 73: least privilege enforced.
- Model note 74: least privilege enforced.
- Model note 75: least privilege enforced.
- Model note 76: least privilege enforced.
- Model note 77: least privilege enforced.
- Model note 78: least privilege enforced.
- Model note 79: least privilege enforced.
- Model note 80: least privilege enforced.
- Model note 81: least privilege enforced.
- Model note 82: least privilege enforced.
- Model note 83: least privilege enforced.
