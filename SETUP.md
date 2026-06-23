# 🔐 SETUP — Add Secrets to GitHub

Go to: **Settings → Secrets and variables → Actions → New repository secret**

Add these 7 secrets:

| Secret Name | How to Get It |
|-------------|---------------|
| `GEMINI_API_KEY` | From https://aistudio.google.com |
| `TELEGRAM_BOT_TOKEN` | From @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | From @userinfobot on Telegram |
| `BUFFER_API_TOKEN` | From buffer.com → Settings → API |
| `GH_PAT` | GitHub → Settings → Developer settings → PAT (classic) → repo+workflow |
| `GITHUB_REPO_OWNER` | `maryamghabel3-debug` |
| `GITHUB_REPO_NAME` | `elina-radman` |

Then: **Settings → Actions → General**
- ✅ Allow all actions
- ✅ Read and write permissions
- ✅ Save

To test: **Actions → Generate Daily Content → Run workflow**
Then Telegram: `/status` to @ElinaRA_bot
