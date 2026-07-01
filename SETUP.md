# 🔐 SETUP — Add Secrets to GitHub

Go to: **Settings → Secrets and variables → Actions → New repository secret**

## Required secrets

| Secret Name | How to Get It |
|-------------|---------------|
| `GEMINI_API_KEY` | From https://aistudio.google.com |
| `TELEGRAM_BOT_TOKEN` | From @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | From @userinfobot on Telegram |
| `GH_PAT` | GitHub → Settings → Developer settings → PAT (classic) → repo+workflow |
| `REPO_OWNER` | `maryamghabel3-debug` |
| `REPO_NAME` | `elina-radman` |

## Publishing (choose Postiz)

| Secret Name | How to Get It |
|-------------|---------------|
| `POSTIZ_API_TOKEN` | Postiz → Settings → API |
| `POSTIZ_URL` | Your Postiz API base URL (e.g. `https://your-postiz/api`) |

## Optional — real trends & analytics (recommended)

| Secret Name | Enables | How to Get It |
|-------------|---------|---------------|
| `YOUTUBE_API_KEY` | Real trending videos + real channel analytics | Google Cloud Console → YouTube Data API v3 (free) |
| `YOUTUBE_CHANNEL_ID` | Real view/like/comment stats for Elina's channel | Your channel's ID |
| `IG_ACCESS_TOKEN` | Real Instagram reach/impressions | Meta Graph API (IG business account) |
| `IG_USER_ID` | Instagram insights | Your IG business account ID |

> Without the optional secrets the system still works: trends fall back to
> Reddit + Google Trends (no key needed) and analytics fall back to clearly
> labelled simulated data.

Then: **Settings → Actions → General**
- ✅ Allow all actions
- ✅ Read and write permissions
- ✅ Save

To test: **Actions → Generate Daily Content → Run workflow**
Then Telegram: `/status` to @ElinaRA_bot
