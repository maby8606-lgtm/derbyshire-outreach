import streamlit as st
import pandas as pd
import sqlite3
import resend
import os
import html
import time
import random
from dotenv import load_dotenv

# Load secrets (local .env for dev; host secrets in production)
load_dotenv()


def get_secret(name, default=None):
    """Read from environment first, then Streamlit secrets.

    Works on: local (.env), Hugging Face (env vars), Render (env vars),
    and Streamlit Community Cloud (st.secrets, also exposed as env vars).
    """
    value = os.getenv(name)
    if value:
        return value
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default


resend.api_key = get_secret("RESEND_API_KEY")
FROM_EMAIL = get_secret("FROM_EMAIL", "hello@yourdomain.com")
APP_PASSWORD = get_secret("APP_PASSWORD")
DB_FILE = "dashboard_targets.db"

# Domain part of FROM_EMAIL, for a valid List-Unsubscribe address.
# (Original code used unsubscribe@<full email>, which is malformed.)
FROM_DOMAIN = FROM_EMAIL.split("@")[-1] if "@" in FROM_EMAIL else FROM_EMAIL

# --- PAGE CONFIG & CUSTOM CSS ---
st.set_page_config(page_title="Derbyshire Bank | Outreach", page_icon="🏦", layout="wide")

st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background-color: #0E1117;
    }
    /* Headers */
    h1, h2, h3 {
        color: #00D2FF !important;
        font-family: 'Helvetica Neue', sans-serif;
    }
    /* Buttons */
    .stButton>button {
        background-color: #00D2FF;
        color: #0E1117;
        font-weight: bold;
        border-radius: 8px;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #008eb3;
        color: white;
    }
    /* Text inputs */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background-color: #1E2329;
        color: white;
        border-radius: 8px;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    </style>
""", unsafe_allow_html=True)

# --- PASSWORD GATE ---
# This app can send email through your Resend key. Never leave it public
# and unauthenticated. Set APP_PASSWORD in host secrets to require it.
if APP_PASSWORD:
    if not st.session_state.get("authenticated"):
        st.title("🏦 Derbyshire Bank | Outreach")
        pwd = st.text_input("Password", type="password")
        if st.button("Unlock", use_container_width=True):
            if pwd == APP_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()
else:
    st.warning(
        "APP_PASSWORD is not set. Anyone with this URL can use this app "
        "and send email through your Resend key. Set APP_PASSWORD in host "
        "secrets, or deploy as a private app."
    )

if not resend.api_key:
    st.error("RESEND_API_KEY is not set. Add it in host secrets before sending.")

# --- DATABASE FUNCTIONS ---
# NOTE: SQLite file lives on ephemeral disk on free hosts (Streamlit Cloud,
# Render free, HF Spaces). Targets/stats reset when the app restarts,
# redeploys, or wakes from sleep on a fresh container. Re-upload your CSV
# after a restart, or move to an external Postgres (e.g. Supabase free)
# if you need durable campaign history.
def setup_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS targets 
                 (id INTEGER PRIMARY KEY, email TEXT UNIQUE, status TEXT)''')
    conn.commit()
    return conn

def load_csv(file):
    df = pd.read_csv(file)
    # Find the email column case-insensitively; fail clearly if missing.
    email_col = next((c for c in df.columns if str(c).strip().lower() == "email"), None)
    if email_col is None:
        raise ValueError(
            f"CSV must contain a column named 'email'. Found columns: {list(df.columns)}"
        )
    conn = setup_db()
    c = conn.cursor()
    added = 0
    skipped = 0
    for _, row in df.iterrows():
        email = str(row[email_col]).strip().lower()
        if not email or "@" not in email or email == "nan":
            skipped += 1
            continue
        try:
            c.execute("INSERT OR REPLACE INTO targets (email, status) VALUES (?, 'pending')", (email,))
            added += 1
        except Exception:
            skipped += 1
    conn.commit()
    conn.close()
    return added, skipped

def get_stats():
    conn = setup_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM targets WHERE status='pending'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM targets WHERE status='sent'")
    sent = c.fetchone()[0]
    conn.close()
    return pending, sent

def reset_db():
    conn = setup_db()
    c = conn.cursor()
    c.execute("UPDATE targets SET status='pending'")
    conn.commit()
    conn.close()

# --- SPINTAX ---
def generate_spintax(text):
    while '{' in text and '}' in text:
        start = text.find('{')
        end = text.find('}') + 1
        options = text[start+1:end-1].split('|')
        text = text[:start] + random.choice(options) + text[end:]
    return text

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830284.png", width=80) # Bank Icon
    st.title("Derbyshire Bank")
    st.markdown("---")
    st.subheader("📊 Campaign Stats")
    
    pending, sent = get_stats()
    
    col_a, col_b = st.columns(2)
    col_a.metric("Pending", pending)
    col_b.metric("Sent", sent)
    
    st.markdown("---")
    st.subheader("⚙️ Controls")
    st.caption(f"Sending via: **{FROM_EMAIL}**")
    st.caption("Storage is temporary on free hosts — stats reset on restart. Re-upload CSV after a restart.")
    
    if st.button("🔄 Reset Campaign Data", use_container_width=True):
        reset_db()
        st.success("Database reset! All emails marked as pending.")
        time.sleep(1)
        st.rerun()

# --- MAIN PAGE ---
st.title("🏦 Derbyshire Bank Outreach Engine")
st.markdown("Secure, high-volume email infrastructure.")
st.divider()

# Tabs for cleaner UX
tab1, tab2 = st.tabs(["📁 1. Upload Targets", "✉️ 2. Compose & Send"])

with tab1:
    st.subheader("Upload Recipient List")
    st.markdown("Upload a `.csv` file containing a column named `email`.")
    uploaded_file = st.file_uploader("", type="csv", label_visibility="collapsed")
    
    if uploaded_file is not None:
        if st.button("Load Emails into Database", use_container_width=True):
            with st.spinner("Processing CSV..."):
                try:
                    count, skipped = load_csv(uploaded_file)
                    st.success(f"Successfully loaded {count} targets! ({skipped} skipped)")
                except Exception as e:
                    st.error(str(e))

with tab2:
    st.subheader("Compose Message")
    st.info("💡 **Pro Tip:** Use Spintax like `{Hello|Hi|Dear}` in your subject and body to avoid spam filters.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        subject_template = st.text_input("Subject Line", "{Quick question|Inquiry|Partnership} for your company")
    with col2:
        st.write("") # Spacer
        st.write("") # Spacer
        st.caption("Spintax is active and will randomize these texts.")
        
    body_template = st.text_area("Email Body", 
        "{Dear|Hello|Hi} there,\n\nI'm reaching out regarding an opportunity at Derbyshire Bank.\n\n{Let me know|Are you open|Would you be interested} in a brief chat?\n\nBest regards,\nThe Derbyshire Team",
        height=250)

    st.divider()
    
    # THE SEND BUTTON
    if st.button("🚀 Launch Campaign", use_container_width=True, type="primary"):
        pending, _ = get_stats()
        
        if not resend.api_key:
            st.error("RESEND_API_KEY is not set. Add it in host secrets before sending.")
        elif pending == 0:
            st.warning("No pending emails to send! Please upload a CSV or reset the database.")
        elif not subject_template or not body_template:
            st.error("Subject and Body cannot be empty!")
        else:
            st.info(f"Starting campaign for {pending} emails...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            conn = setup_db()
            c = conn.cursor()
            c.execute("SELECT id, email FROM targets WHERE status='pending'")
            targets = c.fetchall()
            
            success_count = 0
            
            for i, target in enumerate(targets):
                target_id, email = target
                
                subj = generate_spintax(subject_template)
                body = generate_spintax(body_template)
                # Send proper text + html (original sent plain text as html,
                # so line breaks collapsed in mail clients).
                body_html = html.escape(body).replace("\n", "<br>")
                
                try:
                    params = {
                        "from": f"Derbyshire Bank <{FROM_EMAIL}>",
                        "to": [email],
                        "subject": subj,
                        "text": body,
                        "html": body_html,
                        "headers": {"List-Unsubscribe": f"<mailto:unsubscribe@{FROM_DOMAIN}>"}
                    }
                    resend.Emails.send(params)
                    
                    c.execute("UPDATE targets SET status='sent' WHERE id=?", (target_id,))
                    conn.commit()
                    success_count += 1
                    status_text.text(f"✅ Sent {success_count}/{pending} | Current: {email}")
                    
                except Exception as e:
                    status_text.text(f"❌ Failed: {email} | Error: {e}")
                    
                progress_bar.progress((i + 1) / pending)
                time.sleep(0.5) 
                
            conn.close()
            st.balloons()
            st.success(f"🎉 Campaign Finished! Successfully sent {success_count} emails.")
