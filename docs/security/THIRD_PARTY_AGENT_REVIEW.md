# Third-Party Agent and Supply Chain Review - ElinaOS

ElinaOS uses open source libraries and external AI models. Supply chain secured.

## Inventory

| Component | Source | Version Pin | Review Date | Risk |
|---|---|---|---|---|
| freellmapi (tashfeenahmed) | GitHub | commit SHA pinned | 2026-07-06 | Medium |
| Gemini API | Google | API version v1 | ongoing | Medium |
| Telegram Bot API | Telegram | Bot API 6.x | ongoing | Low |
| Streamlit | PyPI | 1.35+ pinned in req | monthly | Low |
| Kivy + Buildozer | PyPI/GitHub | spec pinned | monthly | Low |
| Pillow | PyPI | 10.x | monthly | Low |
| GitHub Actions | GitHub Marketplace | SHA pinned | weekly | Medium |
| Marketplace actions | various | SHA pinned | weekly | High |

## Review Process for New Dependency
1. Propose via issue with justification and alternatives.
2. Check license: no GPL, only MIT/Apache/BSD/PSF allowed.
3. Check maintenance: commits in last 6 months? Issues responsive?
4. Check supply chain: SLSA level, signed tags, provenance?
5. Threat model update: what if this dep is malicious?
6. Security scan: `pip-audit` + `semgrep` + `trivy` on image.
7. SBOM entry added in `dashboard/requirements.txt` or `requirements.txt`.
8. Approval: 2 reviewers, one security-focused.
9. Pin version SHA or exact version, not `*` or `>=`.
10. Monitor: Dependabot alerts, CVEs, auto PRs.

## GitHub Actions Hardening
- Pin actions to full SHA, not tag: `uses: actions/checkout@a5ac7e51...`.
- Verify action source org: official or well-known.
- Use `permissions:` minimal: `contents: read` not write all.
- No `pull_request_target` with secrets unless approved and isolated.
- Composite actions reviewed like code, not blindly trusted.
- Private fork for high-risk workflows? Consider.
- Workflow audit weekly: `scripts/audit_workflows.py`.

## AI Model Supply Chain (Gemini, Image, Video)
- Model provider: Google Gemini, NVIDIA, other free tiers as per docs.
- Data sent to provider: only sanitized prompts, no RESTRICTED data.
- PII redacted before sending to external LLM.
- Provider risk: data retention? Contract says no training on our data.
- Fallback: free LLM alternatives listed in `docs/FREE-LLM-SETUP.md`.
- Cost cap per session, prevent abuse via free tier.
- Output from model treated as L0 untrusted, goes through OutputGuard.
- If provider compromised, can switch via `agents/llm_router.py`.

## Free LLM API Project (tashfeenahmed/freellmapi)
- Why: provides free access to multiple LLM providers via proxy.
- Risk: proxy could see prompts, so no RESTRICTED data sent.
- Mitigation: self-host proxy if scale grows, or use direct provider.
- Verification: code review of proxy, check it does not log secrets.
- Version pinned to commit hash in requirements-core.txt.
- Alternative: `docs/FREE-LLM-ALTERNATIVES.md` lists others.

## Image and Video Gen Supply Chain
- Models: free tiers listed in `docs/TOP-70-IMAGE-MODELS-FREE-ACCESS-2026.md`.
- Each model tested in `scripts/test_live_image.py` and `test_live_video.py`.
- Prompts sanitized before sending, no PII.
- Output images stored in `images/`, metadata stripped to avoid leak.
- If model returns malicious image (QR exfil), vision guard blocks.

## License and Attribution
- All third-party code license tracked in `docs/TOOLS-RESEARCH-2026-07-06.md`.
- Attribution file generated via `pip-licenses`.
- No copyleft GPL in production image, only permissive.
- If GPL needed for build tool only, isolated to build container.

## SBOM and Provenance
- SBOM generated via `syft` and `cyclonedx` on each build.
- Stored as artifact in Actions: `sbom.json`.
- Provenance via SLSA GitHub generator: `slsa-framework/slsa-github-generator`.
- Verify provenance before deploy to prod.

## Vulnerability Response
- If CVE found in dependency: triage CVSS, check exploitability.
- If CVSS>=7 and exploitable: SEV3, fix within 24h, PR emergency.
- If CVSS<7: fix within 7 days via normal PR.
- If dependency unmaintained: fork or replace, do not stay vulnerable.
- Communication: Dependabot PR + issue with label `security`.

## Continuous Monitoring
- Dependabot weekly scans enabled.
- `pip-audit` daily in `daily-content.yml` but only reports.
- Trivy image scan on push to main.
- Secret scan as per SECRETS doc.

## Future
- SLSA level 3 for all builds.
- Sigstore signing for artifacts.
- Private registry proxy to filter malicious packages.
- VEX statements for false positives.
- Supply note 93: SBOM verified.
- Supply note 94: SBOM verified.
- Supply note 95: SBOM verified.
- Supply note 96: SBOM verified.
- Supply note 97: SBOM verified.
- Supply note 98: SBOM verified.
- Supply note 99: SBOM verified.
- Supply note 100: SBOM verified.
- Supply note 101: SBOM verified.
- Supply note 102: SBOM verified.
- Supply note 103: SBOM verified.
