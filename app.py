# app.py — Cipher Missions + Firebase (FINAL, DISPLAY FIXED)

import streamlit as st
import json, random, time, logging
import os
import re
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from google_auth_oauthlib.flow import Flow
from streamlit.errors import StreamlitSecretNotFoundError

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Agency Intel Ops", layout="centered")
logging.getLogger("streamlit").setLevel(logging.ERROR)

# =========================
# GLOBAL CSS (WHITE TEXT IN DARK BOXES)
# =========================
st.markdown("""
<style>
.dark-box {
    background:#021413;
    color:#ffffff !important;
    padding:14px;
    border-radius:8px;
    font-family: monospace;
    border:1px solid rgba(0,195,122,0.25);
}
.dark-box * {
    color:#ffffff !important;
}
.log-box {
    background:#021413;
    color:#ffffff !important;
    padding:12px;
    border-radius:6px;
    margin-bottom:8px;
    font-family: monospace;
}
</style>
""", unsafe_allow_html=True)

# =========================
# FILES
# =========================
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
WORD_BANK_FILE = APP_DIR / "wordbank.json"

# =========================
# LOAD WORDBANK
# =========================
def _load_wordbank():
    try:
        secrets = st.secrets.get("wordbank", {})
    except StreamlitSecretNotFoundError:
        secrets = {}
    stored = secrets.get("json") or os.getenv("WORDBANK_JSON")
    if stored:
        return json.loads(stored)
    if WORD_BANK_FILE.exists():
        return json.loads(WORD_BANK_FILE.read_text())
    return None

word_bank = _load_wordbank()
if word_bank is None:
    st.error(
        "Missing mission word bank. Add the wordbank JSON to Streamlit "
        "secrets ([wordbank] json) or place wordbank.json beside app.py."
    )
    st.stop()

# =========================
# SESSION STATE DEFAULTS
# =========================
defaults = {
    "auth_email": None,
    "codename": None,
    "oauth_state": None,
    "player": "",
    "uid": None,
    "uid_loaded": False,
    "level": 1,
    "score": 0,
    "mission_started": False,
    "start_time": None,
    "current_entry": None,
    "current_cipher": "",
    "show_clues": False,
    "history": [],
    "hint_uses": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================
# IMPORT GAME + FIREBASE
# =========================
from Cipher import encode_for_level
from database import (
    create_user,
    get_progress,
    update_score,
    update_level,
    increment_hint_usage,
    update_leaderboard,
    save_progress,
    create_account,
    get_account,
    verify_account,
    set_codename,
    upsert_google_account,
    uid_for_email,
)

# =========================
# USER LOADING
# =========================
def load_player(uid, codename):
    """Load (or create) the player's persisted progress for the account uid."""
    create_user(uid, codename)
    data = get_progress(uid)

    if not data:
        save_progress(uid, codename, 1, 0)
        data = {"level": 1, "score": 0, "uses_hint": 0}

    st.session_state.player = codename
    st.session_state.codename = codename
    st.session_state.uid = uid
    st.session_state.level = int(data.get("level", 1))
    st.session_state.score = int(data.get("score", 0))
    st.session_state.hint_uses = int(data.get("uses_hint", 0))
    st.session_state.uid_loaded = True

# =========================
# GOOGLE OAUTH HELPERS
# =========================
def _google_secrets():
    try:
        return st.secrets.get("google", {})
    except StreamlitSecretNotFoundError:
        return {}

def _google_client_config(secret):
    return {
        "web": {
            "client_id": secret["client_id"],
            "client_secret": secret["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

def _google_redirect_base():
    secret = _google_secrets()
    configured = secret.get("redirect_uri") or os.getenv("OAUTH_REDIRECT_URI")
    if configured:
        return configured.rstrip("/")
    try:
        host = st.context.headers.get("Host")
    except Exception:
        host = None
    if host:
        scheme = "http" if host.split(":")[0] in ("localhost", "127.0.0.1") else "https"
        return f"{scheme}://{host}"
    return "http://localhost:8501"

def google_auth_url():
    flow = Flow.from_client_config(
        _google_client_config(_google_secrets()),
        scopes=["openid", "email", "profile"],
    )
    flow.redirect_uri = _google_redirect_base()
    auth_url, state = flow.authorization_url(prompt="select_account")
    st.session_state.oauth_state = state
    return auth_url

def handle_google_callback():
    code = st.query_params.get("code")
    if not code:
        return

    state = st.query_params.get("state")
    if state != st.session_state.get("oauth_state"):
        st.error("Google sign-in failed (state mismatch). Please try again.")
        _clear_oauth_params()
        return

    secret = _google_secrets()
    flow = Flow.from_client_config(
        _google_client_config(secret),
        scopes=["openid", "email", "profile"],
    )
    flow.redirect_uri = _google_redirect_base()
    flow.fetch_token(code=code)
    session = flow.authorized_session()
    info = session.get("https://www.googleapis.com/oauth2/v2/userinfo").json()

    _clear_oauth_params()

    email = (info.get("email") or "").strip().lower()
    if not email:
        st.error("Could not retrieve your Google email.")
        return

    upsert_google_account(email, str(info.get("id") or email))
    st.session_state.auth_email = email
    st.rerun()

def _clear_oauth_params():
    for key in ("code", "state", "scope", "authuser", "prompt", "hd"):
        if key in st.query_params:
            del st.query_params[key]

def validate_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))

# =========================
# LOGIN GATE
# =========================
handle_google_callback()

if not st.session_state.auth_email:
    st.markdown("## 🕵️ Agency Intel Ops — Decryption Terminal")
    st.markdown("### 🔐 Agent Login")
    st.markdown("Sign in to continue your missions.")

    tab_email, tab_google = st.tabs(["Email", "Google"])

    with tab_email:
        with st.form("email_login_form", clear_on_submit=False):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            login_submitted = st.form_submit_button("Log In")

        if login_submitted:
            login_email = (login_email or "").strip().lower()
            if not validate_email(login_email):
                st.error("Enter a valid email address.")
            elif verify_account(login_email, login_password):
                st.session_state.auth_email = login_email
                st.rerun()
            else:
                st.error("Invalid email or password.")

        st.markdown("**New agent? Register below.**")
        with st.form("register_form", clear_on_submit=False):
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            register_submitted = st.form_submit_button("Create Account")

        if register_submitted:
            reg_email = (reg_email or "").strip().lower()
            if not validate_email(reg_email):
                st.error("Enter a valid email address.")
            elif not reg_password or len(reg_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif create_account(reg_email, reg_password):
                st.session_state.auth_email = reg_email
                st.success("Account created. Now choose your codename.")
                st.rerun()
            else:
                st.error("That email is already registered. Log in instead.")

    with tab_google:
        st.markdown("Sign in with your Google account. No password needed.")
        try:
            google_secret = _google_secrets()
            if not (google_secret.get("client_id") and google_secret.get("client_secret")):
                st.info("Google sign-in is not configured yet.")
            else:
                st.link_button("Sign in with Google", google_auth_url())
        except Exception:
            st.info("Google sign-in is not configured yet.")

    st.stop()

if st.session_state.auth_email:
    # Load returning players that already have a codename.
    existing_account = get_account(st.session_state.auth_email) or {}
    if (
        existing_account.get("codename")
        and not st.session_state.uid_loaded
    ):
        load_player(existing_account["uid"], existing_account["codename"])
        start_new_mission()
        st.rerun()

# First-time players choose their codename.
if st.session_state.auth_email and not st.session_state.uid_loaded:
    st.session_state.uid = existing_account.get("uid") or uid_for_email(
        st.session_state.auth_email
    )
    st.markdown("### 🎭 Choose Your Codename")
    st.markdown("Your codename is the callsign shown on the leaderboard.")
    codename = st.text_input("Enter Code Name:")

    if st.button("Confirm Codename"):
        codename = (codename or "").strip()
        if not codename:
            st.error("Codename cannot be empty.")
        else:
            set_codename(st.session_state.auth_email, codename)
            load_player(st.session_state.uid, codename)
            start_new_mission()
            st.rerun()

    st.stop()

# =========================
# MISSION HELPERS
# =========================
def pick_entry(level):
    entries = word_bank.get(str(level), [])
    return random.choice(entries) if entries else None

def start_new_mission():
    entry = pick_entry(st.session_state.level)
    if not entry:
        st.session_state.mission_started = False
        return

    words = [w for w in entry["answer"].upper().split() if w.isalpha()]
    cipher = encode_for_level(words, st.session_state.level)

    st.session_state.current_entry = entry
    # <-- PATCH: use raw cipher as is
    st.session_state.current_cipher = cipher
    st.session_state.start_time = time.time()
    st.session_state.mission_started = True
    st.session_state.show_clues = False

# =========================
# HEADER
# =========================
st.markdown("## 🕵️ Agency Intel Ops — Decryption Terminal")
st.markdown(
    f"**Agent:** {st.session_state.player or '—'} | "
    f"**Level:** {st.session_state.level} | "
    f"**Score:** {st.session_state.score}"
)

# =========================
# INTERCEPTED TRANSMISSION
# =========================
st.markdown("### 📡 Intercepted Transmission")
st.markdown(
    f"<div class='dark-box'>{st.session_state.current_cipher or '— awaiting signal —'}</div>",
    unsafe_allow_html=True
)

# =========================
# STOPWATCH
# =========================
if st.session_state.mission_started:
    elapsed = int(time.time() - st.session_state.start_time)
    st.markdown(f"⏱ **Elapsed Time:** {elapsed} seconds")

# =========================
# HINTS (TWO-STAGE LOGIC)
# =========================
if st.button("💡 Get Hint") and st.session_state.player:

    if not st.session_state.mission_started:
        st.markdown("### Clue meanings")
        st.markdown("""
        **M:** Mission context  
        **I:** Intercepted detail  
        **P:** Physical proof  
        **B:** Backstory  
        **E:** Evidence
        """)
    else:
        e = st.session_state.current_entry
        st.markdown("### Mission Clues")
        st.markdown(
            f"""
            <div class="dark-box">
            <strong>M:</strong> {e['M']}<br>
            <strong>I:</strong> {e['I']}<br>
            <strong>P:</strong> {e['P']}<br>
            <strong>B:</strong> {e['B']}<br>
            <strong>E:</strong> {e['E']}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.session_state.hint_uses += 1
        increment_hint_usage(st.session_state.uid)

# =========================
# ANSWER INPUT (SAFE)
# =========================
if st.session_state.mission_started:
    guess = st.text_input("Enter decoded phrase (exact match):", key="guess_input")

    if st.button("Transmit Conclusion"):
        correct_answer = st.session_state.current_entry["answer"].lower().strip()
        is_correct = guess.lower().strip() == correct_answer

        st.session_state.history.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "level": st.session_state.level,
            "cipher": st.session_state.current_cipher,
            "answer": guess,
            "correct": is_correct
        })

        if is_correct:
            points = 5 + st.session_state.level // 2
            st.session_state.score += points
            st.success(f"✅ Correct! +{points} points")

            update_level(st.session_state.uid, st.session_state.level + 1)
            update_score(st.session_state.uid, st.session_state.score)
            update_leaderboard(st.session_state.player, st.session_state.score)

            st.session_state.level += 1
            st.session_state.mission_started = False
            start_new_mission()
            st.rerun()
        else:
            st.session_state.score = max(0, st.session_state.score - 2)
            st.error("❌ Incorrect. Mission compromised.")
            update_score(st.session_state.uid, st.session_state.score)

# =========================
# RESTART MISSION (NO SKIP)
# =========================
if st.button("♻️ Restart Mission"):
    st.session_state.mission_started = False
    start_new_mission()
    st.rerun()

# =========================
# MISSION LOG (SESSION ONLY)
# =========================
st.markdown("## 🗂 Mission Debrief (Session)")

if st.session_state.history:
    for h in reversed(st.session_state.history):
        status = "SUCCESS" if h["correct"] else "FAILED"
        color = "#00c37a" if h["correct"] else "#ff4b4b"
        st.markdown(
            f"""
            <div class="log-box" style="border-left:5px solid {color};">
            Level {h['level']} — {status}<br>
            Cipher: {h['cipher']}<br>
            Answer: {h['answer']}
            </div>
            """,
            unsafe_allow_html=True
        )
else:
    st.info("No completed missions yet.")