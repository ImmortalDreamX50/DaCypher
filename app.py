# app.py - Full Cipher Missions + Firebase integration with Live Stopwatch
import streamlit as st
import json, random, time, io, wave, logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import uuid

# ---------- AUTH ----------
def get_or_create_uid(codename: str):
    if "uid" not in st.session_state:
        st.session_state.uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, codename))
    return st.session_state.uid

# Cipher imports
from Cipher import encode_for_level, decode_for_level

# Firebase functions
from firebase import (
    create_user,
    get_progress,
    update_score,
    update_level,
    increment_hint_usage,
    update_leaderboard,
    save_progress,
)

# -------------------------
# Config & logging
st.set_page_config(page_title="Agency Intel Ops", layout="centered")
logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.media_file_manager").setLevel(logging.CRITICAL)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LEADERBOARD_FILE = DATA_DIR / "leaderboard.csv"
WORD_BANK_FILE = Path("wordbank.json")

# -------------------------
# Sound generator
def make_tone(frequency=880, duration=0.12, volume=0.3, sample_rate=44100):
    try:
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        note = np.sin(frequency * t * 2 * np.pi) * volume
        audio = (note * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())
        buf.seek(0)
        return buf.read()
    except:
        return None

SND_CORRECT = make_tone(1200, 0.16)
SND_WRONG = make_tone(300, 0.2)
SND_NEW = make_tone(700, 0.08)
SND_HINT = make_tone(900, 0.06)

# -------------------------
# Load wordbank
if not WORD_BANK_FILE.exists():
    st.error(f"Missing {WORD_BANK_FILE.name} in project folder.")
    st.stop()

try:
    word_bank = json.loads(WORD_BANK_FILE.read_text())
except Exception as e:
    st.error(f"Error parsing wordbank.json: {e}")
    st.stop()

# Validate wordbank
def validate_wordbank(wb):
    errs = []
    for key, val in wb.items():
        if not str(key).isdigit():
            errs.append(f"Level key '{key}' not numeric")
            continue
        if not isinstance(val, list) or len(val) == 0:
            errs.append(f"Level {key} must be a non-empty list")
            continue
        for entry in val:
            if not all(k in entry for k in ("M","I","P","B","E","answer")):
                errs.append(f"Level {key} entry missing keys: {list(entry.keys())}")
    return errs

errs = validate_wordbank(word_bank)
if errs:
    st.error("wordbank.json validation errors:")
    for e in errs:
        st.write("- " + e)
    st.stop()

# -------------------------
# Session state defaults
defaults = {
    "player": "", "uid_loaded": False, "uid": None,
    "level": 1, "score": 0, "history": [], "seen_puzzles": set(),
    "mission_started": False, "start_time": None, "timer_mode": None,
    "max_time": 60, "current_entry": None, "current_cipher": "",
    "hint_index": 0, "hint_uses": 0, "show_clues": False
}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# -------------------------
# Local leaderboard helpers
def read_leaderboard_local():
    if LEADERBOARD_FILE.exists():
        try: return pd.read_csv(LEADERBOARD_FILE)
        except: return pd.DataFrame(columns=["name","score","level","date"])
    return pd.DataFrame(columns=["name","score","level","date"])

def save_score_local(name, score, level):
    df = read_leaderboard_local()
    new_row = pd.DataFrame([{
        "name": name, "score": score, "level": level,
        "date": datetime.now(timezone.utc).isoformat()
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(LEADERBOARD_FILE, index=False)

# -------------------------
# Firebase helpers
def ensure_user_loaded(username):
    if not username: return False
    uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, username))
    try: create_user(uid, username)
    except Exception as e: st.error(f"Firebase create_user error: {e}"); return False
    try: data = get_progress(uid)
    except Exception as e: st.error(f"Firebase get_progress error: {e}"); return False
    if not data: data = {"level": 1, "score": 0, "uses_hint": 0}; save_progress(uid, username, 1, 0)
    st.session_state.player = username
    st.session_state.level = int(data.get("level", 1))
    st.session_state.score = int(data.get("score", 0))
    st.session_state.hint_uses = int(data.get("uses_hint", 0))
    st.session_state.uid_loaded = True
    st.session_state.uid = uid
    return True

def persist_user_progress(username):
    uid = st.session_state.uid
    try:
        update_level(uid, int(st.session_state.level))
        update_score(uid, username, int(st.session_state.score))
        update_leaderboard(username, int(st.session_state.score))
    except Exception:
        save_score_local(username, st.session_state.score, st.session_state.level)

# -------------------------
# Mission helpers
def pick_random_entry_for_level(level):
    entries = word_bank.get(str(level), [])
    if not entries: return None
    choice = random.choice(entries)
    key = f"{level}::{choice.get('answer','')}"
    if key in st.session_state.seen_puzzles:
        others = [e for e in entries if f"{level}::{e.get('answer','')}" not in st.session_state.seen_puzzles]
        if others: choice = random.choice(others); key = f"{level}::{choice.get('answer','')}"
    st.session_state.seen_puzzles.add(key)
    return choice

def start_new_mission(level=None):
    if level is None: level = st.session_state.level
    entry = pick_random_entry_for_level(level)
    if not entry: st.session_state.current_entry = None; st.session_state.current_cipher = ""; st.session_state.mission_started = False; return False
    st.session_state.current_entry = entry
    words = [w for w in entry.get("answer","").upper().split() if w.isalpha()]
    cipher = encode_for_level(words, st.session_state.level)
    st.session_state.current_cipher = " ".join(chunk.replace("-", "") for chunk in cipher.split())
    st.session_state.hint_index = 0
    st.session_state.start_time = time.time()
    st.session_state.mission_started = True
    try: st.audio(SND_NEW)
    except: pass
    return True

# -------------------------
# UI CSS
st.markdown("""
<style>
:root { --bg:#071011; --panel:#0b1416; --accent:#00c37a; --muted:#8fb0a4; --card:#071819; }
.main-card { background: linear-gradient(180deg, rgba(10,18,20,0.95), rgba(5,10,11,0.95));
border: 1px solid rgba(0,195,122,0.08); padding: 18px; border-radius: 12px;
box-shadow: 0 6px 24px rgba(0,0,0,0.6); color: #e6fff5; max-width: 930px; margin: 12px auto;
font-family: "Source Code Pro", monospace; }
.title-small { color: var(--accent); font-weight:700; font-size:18px; }
.muted { color: #9bbab0; font-size:13px; }
.transmission { background:#021413; border:1px dashed rgba(0,195,122,0.06); padding:12px;
border-radius:8px; font-family:monospace; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-card'>", unsafe_allow_html=True)
st.markdown(f"<h2>🕵️ Agency Intel Ops — Decryption Terminal</h2>", unsafe_allow_html=True)
st.markdown(f"<div class='muted'>Agent: {st.session_state.player or '—'} | Level {st.session_state.level} | Score {st.session_state.score}</div>", unsafe_allow_html=True)

# -------------------------
# Mission display
st.markdown("### Intercepted Transmission")
st.markdown(f"<div class='transmission'>{st.session_state.current_cipher or '— no active transmission —'}</div>", unsafe_allow_html=True)

# -------------------------
# Live Stopwatch
if st.session_state.mission_started:
    stopwatch_placeholder = st.empty()
    while st.session_state.mission_started:
        elapsed = int(time.time() - st.session_state.start_time)
        stopwatch_placeholder.markdown(f"⏱ Elapsed time: **{elapsed} seconds**")
        time.sleep(1)
        st.experimental_rerun()

# -------------------------
# Clues
st.markdown("### Clues (M / I / P / B / E)")
if st.button("🔎 Reveal Clues"):
    st.session_state.show_clues = True
if st.session_state.show_clues and st.session_state.current_entry:
    e = st.session_state.current_entry
    st.markdown(f"**M:** {e.get('M','')}")
    st.markdown(f"**I:** {e.get('I','')}")
    st.markdown(f"**P:** {e.get('P','')}")
    st.markdown(f"**B:** {e.get('B','')}")
    st.markdown(f"**E:** {e.get('E','')}")

# -------------------------
# User login & mission control
if not st.session_state.uid_loaded:
    username_input = st.text_input("Enter Codename:", key="codename_input")
    if username_input:
        if ensure_user_loaded(username_input):
            st.success(f"Welcome, {username_input}. Progress loaded.")
            start_new_mission()
            st.experimental_rerun()
else:
    st.markdown(f"<div class='muted'>Agent: {st.session_state.player}</div>", unsafe_allow_html=True)

# -------------------------
# Answer submission
guess = st.text_input("Enter decoded phrase (exact match):", key="guess_input")
if st.button("Transmit Conclusion") and st.session_state.current_entry:
    answer = st.session_state.current_entry.get("answer","").strip().lower()
    correct = guess.strip().lower() == answer
    st.session_state.history.append({
        "level": st.session_state.level,
        "cipher": st.session_state.current_cipher,
        "answer": guess,
        "correct": correct,
        "time": datetime.now(timezone.utc).isoformat()
    })
    if correct:
        points = 5 + st.session_state.level // 2
        st.session_state.score += points
        try: st.audio(SND_CORRECT)
        except: pass
        st.success(f"✅ Correct. +{points} points.")
        persist_user_progress(st.session_state.player)
        st.session_state.level += 1
        st.session_state.mission_started = False
        start_new_mission()
        st.experimental_rerun()
    else:
        st.session_state.score = max(0, st.session_state.score - 2)
        try: st.audio(SND_WRONG)
        except: pass
        st.error("❌ Incorrect. Mission compromised.")
        persist_user_progress(st.session_state.player)

# -------------------------
# Hints
if st.button("💡 Get Hint") and st.session_state.current_entry:
    reveal = 1 if st.session_state.hint_uses == 0 else 2
    cost = 0 if st.session_state.hint_uses == 0 else 3
    st.session_state.hint_index = min(len(st.session_state.current_entry.get("answer","")), st.session_state.hint_index + reveal)
    st.session_state.hint_uses += 1
    if cost > 0: st.session_state.score = max(0, st.session_state.score - cost); st.warning(f"-{cost} points (hint)")
    persist_user_progress(st.session_state.player)
    try: st.audio(SND_HINT)
    except: pass
    if st.session_state.hint_index > 0:
        st.info(f"Hint: `{st.session_state.current_entry.get('answer','')[:st.session_state.hint_index]}`")

# -------------------------
# Mission log & leaderboard
st.markdown("## 🗂 Mission Log (this session)")
if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)
    st.dataframe(df[["time","level","cipher","answer","correct"]].reset_index(drop=True))
else:
    st.info("No missions logged yet.")

st.markdown("## 🏆 Leaderboard (local fallback)")
lb = read_leaderboard_local()
if not lb.empty:
    lb_sorted = lb.sort_values(by=["score","date"], ascending=[False, True]).reset_index(drop=True)
    st.table(lb_sorted.head(20))
else:
    st.info("No saved scores yet.")
st.markdown("</div>", unsafe_allow_html=True)
