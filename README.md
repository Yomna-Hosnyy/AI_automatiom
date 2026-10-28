# 🚀 Auto Publish Content Pipeline

This app lets you upload videos, preview metadata for YouTube, Facebook, and Instagram, upload videos directly to Google Drive, and sync record payloads to Supabase for automated n8n processing.

---

## ⚡ Quick Start (1-Click Run on Windows)

Simply double-click **`run.bat`**. 
It will:
1. Automatically install any missing dependencies (`requirements.txt`).
2. Pop open your browser on the first run so you can sign in with your own Google Drive account.
3. Launch the web interface automatically.

---

## 🔑 First-Time Google Drive Login

When you run the app for the first time:
1. A Google sign-in page will open in your default browser.
2. Select your Google account.
3. If you see **"Google hasn’t verified this app"**:
   - Click **Advanced** (bottom left).
   - Click **Go to [App Name] (unsafe)**.
   - Click **Continue / Allow**.
4. A personal `token.json` file will be generated on your computer. Your account is now linked!

> **Note:** If you ever want to switch to a different Google account, simply click the **"🔄 Switch Drive Account"** button in the app's sidebar.

---

## 🛠️ Manual Launch (Alternative)

If you prefer to run it manually from the terminal:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Authorize Google Drive (first time only)
python authenticate.py

# 3. Start the application
streamlit run app.py
```

---

## 📁 What is Inside this Folder?

- `app.py`: Main Streamlit web application.
- `authenticate.py`: Standalone Google Drive OAuth login helper.
- `client_secret.json`: OAuth Client ID allowing the app to request Drive permissions.
- `.env`: Database credentials (`SUPABASE_URL` and `SUPABASE_KEY`).
- `requirements.txt`: Python package requirements.
- `run.bat`: 1-click Windows launcher.
