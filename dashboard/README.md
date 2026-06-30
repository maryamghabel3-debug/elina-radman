# Streamlit Dashboard Deployment

To deploy this dashboard for free (so it runs 24/7 online without needing your computer):
1. Go to [Streamlit Community Cloud](https://share.streamlit.io/)
2. Sign in with your GitHub account.
3. Click "New App".
4. Select your repository `maryamghabel3-debug/elina-radman`.
5. Branch: `main`
6. Main file path: `dashboard/app.py`
7. Click "Advanced Settings" and paste your secrets (HF_TOKEN, GEMINI_API_KEY) in the Secrets box like this:
   ```toml
   HF_TOKEN="your_token"
   GEMINI_API_KEY="your_key"
   ```
8. Click Deploy!
