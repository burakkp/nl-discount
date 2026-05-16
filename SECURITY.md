# Security Notes

## ⚠️ Action Required: Rotate Exposed Credentials

The following credentials were **previously committed to git history** and must be rotated immediately, even though they have since been removed from the codebase.

### 1. Firebase Service Account Private Key
- **Status:** Was committed in commit `39bf7d3` — ROTATE IMMEDIATELY
- **Action:** Go to [Firebase Console](https://console.firebase.google.com) → Project Settings → Service Accounts → Generate New Private Key
- Update `FIREBASE_CREDENTIALS_JSON` in your Render environment variables with the new key

### 2. Gemini API Key
- **Status:** Was in `.env` which was committed in `39bf7d3`
- **Action:** Go to [Google AI Studio](https://aistudio.google.com/apikey) → Revoke old key → Create new key
- Update `GEMINI_API_KEY` in Render environment variables

### 3. Firebase Web API Key / Google Places API Key
- These are **client-side keys** designed to be public — no rotation needed
- Protect them using [Firebase Security Rules](https://firebase.google.com/docs/rules) and [API key restrictions](https://console.cloud.google.com/apis/credentials) (restrict to your app's bundle ID and SHA-1)

## ✅ Current Security Posture (after fixes)

- `.env` is in `.gitignore` and will never be committed again
- All credentials read from environment variables only
- `docker-compose.yml` uses env var substitution (`${VAR:-default}`)
- Hardcoded local DB passwords removed from `seed_stores.py` and `patch_db.py`
- `.env.example` provides a safe template for new developers

## Environment Variable Setup

For local development, copy `.env.example` to `.env` and fill in real values:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

For production (Render), set all variables in the Render dashboard Environment tab.
