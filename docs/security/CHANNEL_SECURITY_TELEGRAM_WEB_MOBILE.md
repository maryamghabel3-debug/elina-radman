# Channel Security - Telegram, Web, Mobile - ElinaOS

TARGET: Each channel isolated with distinct auth, rate limits, privacy controls.

## Telegram Bot Channel
- TARGET: Bot token stored in vault, rotated every 90 days, never in code.
- Bot offset tracked in `content/bot_offset.txt`, persisted safely.
- Commands allowlisted: /start, /generate, /status, /publish.
- TARGET: All inputs go through InputGuard + Prompt Injection Defense.
- No direct DB write: bot emits queue JSON, worker validates.
- TARGET: Rate limit: 20 msg/min per user, 100/min globally, burst 10.
- Privacy: no PII stored beyond Telegram user_id hash.
- TARGET: If BIDI or RTL override chars detected, message quarantined.
- TARGET: Telegram webhook validated via secret token header.
- Channel runs in isolated worker, no access to secrets store.

## Web Dashboard Channel
- Dashboard at `dashboard/app.py`, Streamlit hardened config.
- TARGET: Auth: signed JWT, HttpOnly, Secure, SameSite=Lax, 15m expiry.
- TARGET: CSRF protection via double-submit cookie.
- TARGET: CSP header: default-src self, no inline scripts.
- TARGET: API endpoints rate limited: 60 req/min per IP.
- File upload: MIME sniff, max 5MB, virus scan stub.
- No eval, no pickle load, no dynamic code execution.
- Web egress blocked to 169.254.*, 10.*, 172.16.*, 192.168.*.
- Session logs show IP hash + UA, not raw IP.

## Mobile App Channel (Kivy/Buildozer)
- App spec in `app/buildozer.spec`, permissions minimal.
- No extra permissions: no SMS, no contacts, no location unless needed.
- TARGET: Storage encrypted using Android Keystore / iOS Keychain.
- TARGET: Certificate pinning for api.github.com and backend.
- Deep links validated against allowlist, no open redirect.
- WebView disabled or with safe browsing enabled.
- TARGET: Local DB: SQLCipher AES-256, key derived from user PIN + device ID.

## Privacy Limits
- Data minimization: collect only what is needed for feature.
- Retention: 90 days for logs, 7 days for temp content, then purge.
- User can request deletion via `/delete_data` + confirmation.
- No third-party analytics without opt-in.

## API Security (Shared)
- All APIs require Authorization header, Bearer short-lived token.
- Tokens scoped: `read:content`, `write:content`, `admin:publish`.
- CORS allowlist: dashboard domain only, no wildcard.
- Idempotency key required for publish to prevent double post.
- Response headers: X-Content-Type-Options nosniff, X-Frame DENY.

## Abuse Prevention
- IP reputation check on Telegram + Web: block if flagged.
- CAPTCHA after 3 failed auth attempts.
- Content filter: NSFW and hate speech blocked before publish.
- Automated alerts on spike: >500 requests in 5m triggers ALERT.

## Audit and Monitoring
- Per-channel event stream: telegram.events, web.events, mobile.events.
- TARGET: Central SIEM correlates cross-channel anomalies.
- Dashboard shows real-time channel health and block rate.

## Secure Defaults Checklist
- TARGET: [x] No hardcoded tokens in repo, vault only.
- TARGET: [x] Rate limits defined in code, not just infra.
- TARGET: [x] Privacy policy linked in README.
- [x] Dependency scan weekly.

## Incident Contacts
- Telegram channel admin: owner GitHub account.
- Web incident: rollback via GitHub Actions, disable bot-runner.yml.
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
