# Derbyshire Bank Outreach

Streamlit outreach dashboard. Upload a CSV with an `email` column, compose with spintax, send via Resend.

## Deploy (Streamlit Community Cloud — free)
1. Push this folder to GitHub (do NOT commit `.streamlit/secrets.toml` or `.env`).
2. share.streamlit.io → sign in with GitHub → Create app → repo / branch `main` / main file `app.py`.
3. Advanced settings → Secrets → paste:
   ```
   RESEND_API_KEY = "re_..."
   FROM_EMAIL = "hello@financordirtytalk.com"
   APP_PASSWORD = "choose-a-strong-password"
   ```
4. Deploy as a **private** app if possible. Test with a send to your own inbox first.

## Notes
- `FROM_EMAIL` domain must be verified in Resend (SPF/DKIM) or sends fail.
- SQLite storage is ephemeral on free hosts: campaign stats reset on restart/redeploy. Re-upload CSV after a restart.
- Set `APP_PASSWORD` — without it, anyone with the URL can send through your Resend key.
- Only email people who consented / have a lawful basis, include a working unsubscribe and your postal address, and respect Resend + mailbox-provider rate limits.

## Local run
```
pip install -r requirements.txt
streamlit run app.py
```
Put keys in `.env` locally (never commit it).
