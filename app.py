# app.py — Agency Intel Ops (Final Clean Version)

import streamlit as st
import json, random, time, logging, re
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import uuid

# ================= CONFIG =================
st.set_page_config(page_title="Agency Intel Ops", layout="centered")
logging.getLogger("streamlit").setLevel(logging.ERROR)

# ================= FILES =================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LEADERBOARD_FILE = DATA_DIR / "leaderboard.csv"
WORD_BANK_FILE = Path("wordbank.json")

# ================= LOAD WORDBANK =================
if not WORD_BANK_FILE.exists():
    st.error("wordbank.json missing.")
    st.stop()

word_bank = json.loads(WORD_BANK_FILE.read_text())

# ================= SESSION DEFAULTS =================
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
    "seen_puzzles": set(),
    "hint_uses": 0
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ================= FIREBASE =================
from Cipher import encode_for_level
from firebase import (
    create_user, get_progress,
    update_score, update_level,
    update_leaderboard, save_progress
)

def ensure_user(username):
    uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, username))
    create_user(uid, username)
    data = get_progress(uid) or {"level": 1, "score": 0, "uses_hint": 0}
    st.session_state.update({
        "player": username,
        "uid": uid,
        "level": int(data["level"]),
        "score": int(data["score"]),
        "hint_uses": int(data["uses_hint"]),
        "uid_loaded": True
    })

def persist():
    update_level(st.session_state.uid, st.session_state.level)
    update_score(st.session_state.uid, st.session_state.player, st.session_state.score)
    update_leaderboard(st.session_state.player, st.session_state.score)

# ================= MISSION =================
def pick_entry(level):
    entries = word_bank.get(str(level), [])
    random.shuffle(entries)
    for e in entries:
        key = f"{level}:{e['answer']}"
        if key not in st.session_state.seen_puzzles:
            st.session_state.seen_puzzles.add(key)
            return e
    return None

def style_cipher(text):
    return "".join(
        f"<span style='color:white'>{c}</span>" if c.isdigit() else c
        for c in text
    )

def start_mission():
    entry = pick_entry(st.session_state.level)
    if not entry:
        st.session_state.mission_started = False
        return

    words = entry["answer"].upper().split()
    cipher = encode_for_level(words, st.session_state.level)

    st.session_state.update({
        "current_entry": entry,
        "current_cipher": style_cipher(cipher),
        "mission_started": True,
        "start_time": time.time(),
        "show_clues": False
    })

# ================= UI =================
st.markdown("<div style='max-width:900px;margin:auto;'>", unsafe_allow_html=True)
st.markdown("## 🕵️ Agency Intel Ops — Decryption Terminal")
st.markdown(
    f"<div style='color:#9bbab0'>Agent: {st.session_state.player or '—'} | "
    f"Level {st.session_state.level} | Score {st.session_state.score}</div>",
    unsafe_allow_html=True
)

# ================= LOGIN =================
if not st.session_state.uid_loaded:
    name = st.text_input("Enter Codename:")
    if name:
        ensure_user(name)
        start_mission()
        st.rerun()

# ================= TRANSMISSION =================
st.markdown("### 📡 Intercepted Transmission")
st.markdown(
    f"""
    <div style="
        background:#021413;
        border:1px solid rgba(0,195,122,0.25);
        padding:16px;
        border-radius:10px;
        font-family:monospace;
        color:#00c37a;
        letter-spacing:2px;
        box-shadow:0 0 15px rgba(0,195,122,0.15);
    ">
        {st.session_state.current_cipher or "<span style='opacity:.5'>— awaiting signal —</span>"}
    </div>
    """,
    unsafe_allow_html=True
)

# ================= TIMER =================
if st.session_state.mission_started:
    elapsed = int(time.time() - st.session_state.start_time)
    st.markdown(f"⏱ **Mission Time:** {elapsed}s")

# ================= CLUES =================
st.markdown("### 🧩 Clues")

if st.button("💡 Get Hint"):
    if not st.session_state.mission_started:
        st.markdown("""
        **M** — Mission context  
        **I** — Intercepted detail  
        **P** — Physical proof  
        **B** — Backstory  
        **E** — Evidence
        """)
    else:
        st.session_state.show_clues = True
        st.session_state.hint_uses += 1
        persist()

if st.session_state.show_clues and st.session_state.current_entry:
    e = st.session_state.current_entry
    st.markdown(
        f"""
        <div style="background:#010b0a;padding:14px;border-radius:8px;">
        <strong>M:</strong> {e['M']}<br>
        <strong>I:</strong> {e['I']}<br>
        <strong>P:</strong> {e['P']}<br>
        <strong>B:</strong> {e['B']}<br>
        <strong>E:</strong> {e['E']}
        </div>
        """,
        unsafe_allow_html=True
    )

# ================= ANSWER =================
if st.session_state.mission_started:
    guess = st.text_input("Enter decoded phrase (exact match):")

    if st.button("📤 Transmit Conclusion"):
        correct = guess.strip().lower() == st.session_state.current_entry["answer"].lower()

        st.session_state.history.append({
            "level": st.session_state.level,
            "cipher": re.sub("<.*?>", "", st.session_state.current_cipher),
            "answer": guess,
            "correct": correct,
            "time": datetime.now(timezone.utc).isoformat()
        })

        if correct:
            st.success("✅ Decryption confirmed.")
            st.session_state.score += 5
            st.session_state.level += 1
            persist()
            start_mission()
            st.rerun()
        else:
            st.error("❌ Incorrect. Transmission lost.")
            st.session_state.score = max(0, st.session_state.score - 2)
            persist()

# ================= SESSION LOG =================
st.markdown("## 🗂 Mission Debrief (Session Only)")

if st.session_state.history:
    for h in reversed(st.session_state.history):
        color = "#00c37a" if h["correct"] else "#ff4b4b"
        status = "SUCCESS" if h["correct"] else "FAILED"
        st.markdown(
            f"""
            <div style="border-left:5px solid {color};
                        background:#021413;
                        padding:12px;
                        margin-bottom:8px;
                        font-family:monospace;">
            Level {h['level']} — {status}<br>
            Answer: {h['answer']}
            </div>
            """,
            unsafe_allow_html=True
        )
else:
    st.info("No missions completed yet.")

# ================= RESTART =================
if st.button("♻️ Restart Session"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

st.markdown("</div>", unsafe_allow_html=True)
