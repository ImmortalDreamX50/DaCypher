# app.py — Cipher Missions + Firebase (FINAL, FIXED)

import streamlit as st
import json, random, time, logging, uuid
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

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
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
WORD_BANK_FILE = Path("wordbank.json")

# =========================
# LOAD WORDBANK
# =========================
if not WORD_BANK_FILE.exists():
    st.error("Missing wordbank.json")
    st.stop()

word_bank = json.loads(WORD_BANK_FILE.read_text())

# =========================
# SESSION STATE DEFAULTS
# =========================
defaults = {
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
from firebase import (
    create_user,
    get_progress,
    update_score,
    update_level,
    increment_hint_usage,
    update_leaderboard,
    save_progress,
)

# =========================
# USER LOADING
# =========================
def ensure_user_loaded(username):
    uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, username))
    create_user(uid, username)
    data = get_progress(uid)

    if not data:
        save_progress(uid, username, 1, 0)
        data = {"level": 1, "score": 0, "uses_hint": 0}

    st.session_state.player = username
    st.session_state.uid = uid
    st.session_state.level = int(data.get("level", 1))
    st.session_state.score = int(data.get("score", 0))
    st.session_state.hint_uses = int(data.get("uses_hint", 0))
    st.session_state.uid_loaded = True

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
    st.session_state.current_cipher = " ".join(c.replace("-", "") for c in cipher.split())
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
# CODE NAME INPUT
# =========================
if not st.session_state.uid_loaded:
    codename = st.text_input("Enter Codename:")
    if codename:
        ensure_user_loaded(codename)
        start_new_mission()
        st.rerun()

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
            update_score(st.session_state.uid, st.session_state.player, st.session_state.score)
            update_leaderboard(st.session_state.player, st.session_state.score)

            st.session_state.level += 1
            st.session_state.mission_started = False
            start_new_mission()
            st.rerun()
        else:
            st.session_state.score = max(0, st.session_state.score - 2)
            st.error("❌ Incorrect. Mission compromised.")
            update_score(st.session_state.uid, st.session_state.player, st.session_state.score)

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
