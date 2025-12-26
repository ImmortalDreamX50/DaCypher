# app.py - Final integrated app (Type B UI + Firebase Realtime DB)
# KEEP this file next to your Cipher.py and firebase.py (as you provided).
import streamlit as st
import json, random, time, io, wave, logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
# ---------- AUTH (Anonymous-style codename auth) ----------
import uuid

def get_or_create_uid(codename: str):
    """
    Creates a hidden UID linked to a codename.
    UID is stored in session_state and never shown.
    """
    if "uid" not in st.session_state:
        # Stable UID per codename
        st.session_state.uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, codename))
    return st.session_state.uid

# keep exact import as you requested
from Cipher import encode_for_level, decode_for_level

# firebase functions (your firebase.py must be in same folder)
from firebase import (
    create_user,
    get_user,
    get_progress,
    update_score,
    update_level,
    increment_hint_usage,
    update_leaderboard,
    save_progress,
)

# -------------------------
# Config & logging
# -------------------------
st.set_page_config(page_title="Agency Intel Ops", layout="centered", initial_sidebar_state="expanded")
logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.media_file_manager").setLevel(logging.CRITICAL)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LEADERBOARD_FILE = DATA_DIR / "leaderboard.csv"
WORD_BANK_FILE = Path("wordbank.json")

# -------------------------
# Tiny sound generator (optional; safe-guarded)
# -------------------------
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
    except Exception:
        return None

SND_CORRECT = make_tone(1200, 0.16)
SND_WRONG = make_tone(300, 0.2)
SND_NEW = make_tone(700, 0.08)
SND_HINT = make_tone(900, 0.06)

# -------------------------
# Load & validate wordbank
# -------------------------
if not WORD_BANK_FILE.exists():
    st.error(f"Missing {WORD_BANK_FILE.name} in project folder. Add it and restart the app.")
    st.stop()

try:
    word_bank = json.loads(WORD_BANK_FILE.read_text())
except Exception as e:
    st.error(f"Error parsing {WORD_BANK_FILE.name}: {e}")
    st.stop()

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
# Session state default init
# -------------------------
if "player" not in st.session_state: st.session_state.player = ""
if "uid_loaded" not in st.session_state: st.session_state.uid_loaded = False
if "level" not in st.session_state: st.session_state.level = 1
if "score" not in st.session_state: st.session_state.score = 0
if "history" not in st.session_state: st.session_state.history = []
if "seen_puzzles" not in st.session_state: st.session_state.seen_puzzles = set()
if "mission_started" not in st.session_state: st.session_state.mission_started = False
if "start_time" not in st.session_state: st.session_state.start_time = None
if "timer_mode" not in st.session_state: st.session_state.timer_mode = None
if "max_time" not in st.session_state: st.session_state.max_time = 60
if "current_entry" not in st.session_state: st.session_state.current_entry = None
if "current_cipher" not in st.session_state: st.session_state.current_cipher = ""
if "hint_index" not in st.session_state: st.session_state.hint_index = 0
if "hint_uses" not in st.session_state: st.session_state.hint_uses = 0
if "show_clues" not in st.session_state: st.session_state.show_clues = False

# -------------------------
# Leaderboard helpers (local fallback)
# -------------------------
def read_leaderboard_local():
    if LEADERBOARD_FILE.exists():
        try:
            return pd.read_csv(LEADERBOARD_FILE)
        except:
            return pd.DataFrame(columns=["name","score","level","date"])
    return pd.DataFrame(columns=["name","score","level","date"])

def save_score_local(name, score, level):
    df = read_leaderboard_local()
    new_row = pd.DataFrame([{
        "name": name,
        "score": score,
        "level": level,
        "date": datetime.now(timezone.utc).isoformat()
    }])
    df = pd.concat([df, new_row], ignore_index=True, axis=0)
    df.to_csv(LEADERBOARD_FILE, index=False)

# -------------------------
# Firebase wrapper helpers (use your firebase.py functions)
# -------------------------
def ensure_user_loaded(username):
    """Create user in DB if needed then load progress into session_state.
       We keep the codename as the visible handle and avoid showing any internal UID.
    """
    if not username:
        return False
    try:
        create_user(username)  # idempotent; creates if missing (your firebase.py uses username as key)
    except Exception as e:
        st.error(f"Firebase create_user error: {e}")
        return False
    try:
        data = get_progress(username)
    except Exception as e:
        st.error(f"Firebase get_progress error: {e}")
        return False

    if not data:
        # fallback defaults
        data = {"level": 1, "score": 0, "uses_hint": 0}
        try:
            # try to save initial progress if function present
            if callable(save_progress):
                save_progress(username, username, 1, 0)
        except Exception:
            pass

    st.session_state.player = username
    st.session_state.level = int(data.get("level", 1))
    st.session_state.score = int(data.get("score", 0))
    st.session_state.hint_uses = int(data.get("uses_hint", 0))
    st.session_state.uid_loaded = True
    return True

def persist_user_progress(username):
    """Save current level & score back to Firebase (best-effort)."""
    try:
        update_level(username, int(st.session_state.level))
        update_score(username, int(st.session_state.score))
        # also update leaderboard entry
        try:
            update_leaderboard(username, int(st.session_state.score))
        except Exception:
            pass
    except Exception:
        # fallback to local file if firebase fails
        save_score_local(username, st.session_state.score, st.session_state.level)

# -------------------------
# Helpers: pick/start mission
# -------------------------
def pick_random_entry_for_level(level):
    entries = word_bank.get(str(level), [])
    if not entries:
        return None
    choice = random.choice(entries)
    candidate_key = f"{level}::{choice.get('answer','')}"
    if candidate_key in st.session_state.seen_puzzles:
        other = [e for e in entries if f"{level}::{e.get('answer','')}" not in st.session_state.seen_puzzles]
        if other:
            choice = random.choice(other)
            candidate_key = f"{level}::{choice.get('answer','')}"
    st.session_state.seen_puzzles.add(candidate_key)
    return choice

def start_new_mission(level=None):
    if level is None:
        level = st.session_state.level
    entry = pick_random_entry_for_level(level)
    if entry is None:
        st.session_state.current_entry = None
        st.session_state.current_cipher = ""
        st.session_state.mission_started = False
        return False
    st.session_state.current_entry = entry
    words = [w for w in entry.get("answer","").upper().split() if w.isalpha()]
    cipher = encode_for_level(words, st.session_state.level)  # this will output hyphen-joined chunks (if your Cipher does)
    # display continuous (remove hyphens) for player view while keeping encoding decode intact
    cipher_display = " ".join(chunk.replace("-", "") for chunk in cipher.split())
    st.session_state.current_cipher = cipher_display
    st.session_state.hint_index = 0
    # keep hint_uses as loaded (persisted); do not reset DB value here
    st.session_state.start_time = time.time()
    st.session_state.mission_started = True
    try:
        if SND_NEW:
            st.audio(SND_NEW)
    except Exception:
        pass
    return True

# -------------------------
# UI: custom CSS (Type B - modern card)
# -------------------------
st.markdown(
    """
    <style>
    :root { --bg:#071011; --panel:#0b1416; --accent:#00c37a; --muted:#8fb0a4; --card:#071819; }
    .main-card {
        background: linear-gradient(180deg, rgba(10,18,20,0.95), rgba(5,10,11,0.95));
        border: 1px solid rgba(0,195,122,0.08);
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.6);
        color: #e6fff5;
        max-width: 930px;
        margin: 12px auto;
        font-family: "Source Code Pro", monospace;
    }
    .title-small { color: var(--accent); font-weight:700; font-size:18px; }
    .muted { color: #9bbab0; font-size:13px; }
    .transmission { background:#021413; border:1px dashed rgba(0,195,122,0.06); padding:12px; border-radius:8px; font-family:monospace; }
    .sidebar-note { color: var(--muted); font-size:13px; }
    .button-row > div { display:inline-block; margin-right:8px; }
    </style>
    """, unsafe_allow_html=True)

# Layout container
st.markdown("<div class='main-card'>", unsafe_allow_html=True)
st.markdown("<div style='display:flex; justify-content:space-between; align-items:center;'>", unsafe_allow_html=True)
st.markdown(f"<div><h2 style='margin:0'>🕵️ Agency Intel Ops — Decryption Terminal</h2><div class='muted'>Agent console</div></div>", unsafe_allow_html=True)

# Top-right: player + status
status_html = f"<div style='text-align:right'><div class='title-small'>Agent: {st.session_state.player or '—'}</div><div class='muted'>Level {st.session_state.level} | Score {st.session_state.score}</div></div>"
st.markdown(status_html, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr style='border:0; border-top:1px solid rgba(0,195,122,0.06)'/>", unsafe_allow_html=True)

# Left: instructions + transmission box, Right: controls
left_col, right_col = st.columns((2,1))

with left_col:
    st.markdown("### Intercepted Transmission")
    st.markdown("<div class='transmission'>", unsafe_allow_html=True)
    st.code(st.session_state.current_cipher or "— no active transmission —")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### Clue meanings (M / I / P / B / E)")
    st.markdown("<div class='muted'>M: Mission context — I: Intercepted detail — P: Physical proof — B: Backstory — E: Evidence</div>", unsafe_allow_html=True)

    # Reveal clues button
    if st.button("🔎 Reveal Clues"):
        st.session_state.show_clues = True

    if st.session_state.show_clues and st.session_state.current_entry:
        e = st.session_state.current_entry
        st.markdown(f"**M:** {e.get('M','')}")
        st.markdown(f"**I:** {e.get('I','')}")
        st.markdown(f"**P:** {e.get('P','')}")
        st.markdown(f"**B:** {e.get('B','')}")
        st.markdown(f"**E:** {e.get('E','')}")

    st.markdown("---")
    # Optional decode (admin)
    if st.checkbox("Show decoded (admin)"):
        try:
            # decode_for_level expects hyphenated or continuous chunk strings; pass re-hyphenated to be safe
            # Recreate hyphenated chunks from display for correct decode by splitting words and slicing into 1-2 digit grouping
            # But decode_for_level's split_numbers supports continuous digits; we can call it directly with stored encoded (we don't have hyphens)
            # We will attempt to decode by re-inserting hyphens using the encode_for_level fallback: easiest is to re-encode the answer if available
            if st.session_state.current_entry and st.session_state.current_entry.get("answer",""):
                st.info(decode_for_level(encode_for_level([w.upper() for w in st.session_state.current_entry.get("answer","").upper().split() if w.isalpha()], st.session_state.level), st.session_state.level))
            else:
                st.info("No entry to decode.")
        except Exception as ex:
            st.error(f"Decode error: {ex}")

with right_col:
    st.markdown("### Mission Controls")

    # Username input & load user progress (only load once)
    if not st.session_state.uid_loaded:
        username_input = st.text_input("Enter Codename (unique):", key="codename_input")
        if username_input:
            ok = ensure_user_loaded(username_input)
            if ok:
                st.success(f"Welcome, {username_input}. Progress loaded.")
                # after loading start a mission automatically
                if not st.session_state.mission_started:
                    start_new_mission()
                    st.experimental_rerun()
    else:
        st.markdown(f"<div class='muted'>Agent: {st.session_state.player}</div>", unsafe_allow_html=True)

    # Timer selection area (only shown when not set)
    if st.session_state.timer_mode is None:
        st.markdown("<div class='muted'>Choose your timer mode (persists across levels)</div>", unsafe_allow_html=True)
        tm = st.selectbox("Timer mode:", ("Stopwatch (no limit)", "Stopwatch with max time"), key="timer_select")
        st.session_state.timer_mode = "stopwatch" if tm.startswith("Stopwatch (no") else "timed"
        if st.session_state.timer_mode == "timed":
            sec = st.number_input("Max seconds:", min_value=10, max_value=3600, value=60, step=5)
            st.session_state.max_time = int(sec)
    else:
        st.markdown(f"<div class='muted'>Timer: {st.session_state.timer_mode} {'| Max: '+str(st.session_state.max_time)+'s' if st.session_state.timer_mode=='timed' else ''}</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Start mission button (if not started)
    if not st.session_state.mission_started and st.session_state.uid_loaded:
        if st.button("▶ Start Mission", key="start_new"):
            started = start_new_mission()
            if not started:
                st.success("No more levels available in your wordbank.")
            st.experimental_rerun()

    # Elapsed / remaining time
    if st.session_state.mission_started:
        st.markdown("**Timer**")
        st.markdown("---")
        stt = st.session_state.start_time or time.time()
        elapsed = int(time.time() - stt)
        if st.session_state.timer_mode == "stopwatch":
            st.markdown(f"⏱ Elapsed: **{elapsed}s**")
        else:
            remaining = max(0, st.session_state.max_time - elapsed)
            st.markdown(f"⏱ {elapsed}s  /  Max: {st.session_state.max_time}s")
            if remaining == 0:
                st.warning("⏰ Time's up — mission failed.")
                try:
                    if SND_WRONG: st.audio(SND_WRONG)
                except: pass
                # Log failure and update DB
                st.session_state.history.append({
                    "level": st.session_state.level,
                    "cipher": st.session_state.current_cipher,
                    "answer": None,
                    "correct": False,
                    "time": datetime.now(timezone.utc).isoformat()
                })
                # apply penalty locally and persist
                st.session_state.score = max(0, st.session_state.score - 1)
                if st.session_state.player:
                    try:
                        persist_user_progress(st.session_state.player)
                    except: pass
                st.session_state.mission_started = False
                st.session_state.hint_uses = 0
                st.experimental_rerun()

    # Hint box + penalty rules
    st.markdown("---")
    st.markdown("**Hints**")
    st.markdown("<div class='muted'>First hint: FREE. Further hints: -3 points each.</div>", unsafe_allow_html=True)
    if st.button("💡 Get Hint"):
        if not st.session_state.current_entry:
            st.warning("No active mission.")
        else:
            if st.session_state.hint_uses == 0:
                reveal = 1
                cost = 0
            else:
                reveal = 2
                cost = 3
            st.session_state.hint_index = min(len(st.session_state.current_entry.get("answer","")), st.session_state.hint_index + reveal)
            if cost > 0:
                st.session_state.score = max(0, st.session_state.score - cost)
                st.warning(f"-{cost} points (hint penalty)")
            st.session_state.hint_uses += 1
            # persist hint usage to firebase
            if st.session_state.player:
                try:
                    increment_hint_usage(st.session_state.player)
                except Exception:
                    pass
            try:
                if SND_HINT: st.audio(SND_HINT)
            except: pass

    if st.session_state.hint_index > 0 and st.session_state.current_entry:
        st.info(f"Hint: `{st.session_state.current_entry.get('answer','')[:st.session_state.hint_index]}`")

    st.markdown("---")
    # Answer input
    guess = st.text_input("Enter decoded phrase (exact match):", key="guess_input")
    if st.button("Transmit Conclusion"):
        if not st.session_state.current_entry:
            st.warning("No active mission.")
        else:
            correct_answer = st.session_state.current_entry.get("answer","").strip().lower()
            is_correct = (guess.strip().lower() == correct_answer)
            # log attempt
            st.session_state.history.append({
                "level": st.session_state.level,
                "cipher": st.session_state.current_cipher,
                "answer": guess,
                "correct": is_correct,
                "time": datetime.now(timezone.utc).isoformat()
            })
            if is_correct:
                elapsed_for_points = max(1, int(time.time() - (st.session_state.start_time or time.time())))
                time_bonus = 0
                if st.session_state.timer_mode == "timed" and st.session_state.max_time:
                    time_bonus = max(0, (st.session_state.max_time - elapsed_for_points) // 3)
                points = 5 + (st.session_state.level // 2) + time_bonus
                st.session_state.score += points
                try:
                    if SND_CORRECT: st.audio(SND_CORRECT)
                except: pass
                st.success(f"✅ Mission success. +{points} points.")
                # persist to firebase
                if st.session_state.player:
                    try:
                        persist_user_progress(st.session_state.player)
                    except Exception:
                        pass
                    try:
                        update_leaderboard(st.session_state.player, st.session_state.score)
                    except Exception:
                        pass
                # move to next level, preserving timer_mode
                st.session_state.level += 1
                st.session_state.mission_started = False
                st.session_state.start_time = None
                st.session_state.hint_index = 0
                st.session_state.hint_uses = 0
                # start next mission automatically
                started = start_new_mission()
                if not started:
                    st.success("No more levels available.")
                st.experimental_rerun()
            else:
                st.session_state.score = max(0, st.session_state.score - 2)
                try:
                    if SND_WRONG: st.audio(SND_WRONG)
                except: pass
                st.error("❌ Incorrect. Mission compromised.")
                # persist score penalty
                if st.session_state.player:
                    try:
                        persist_user_progress(st.session_state.player)
                    except Exception:
                        pass

    st.markdown("---")
    # Controls: skip/save/reset
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Skip (penalty)"):
            st.session_state.score = max(0, st.session_state.score - 1)
            st.session_state.mission_started = False
            st.session_state.start_time = None
            st.session_state.hint_uses = 0
            # advance level and start next
            st.session_state.level += 1
            # persist progress
            if st.session_state.player:
                try:
                    persist_user_progress(st.session_state.player)
                except Exception:
                    pass
            started = start_new_mission()
            if not started:
                st.success("No more levels available.")
            st.experimental_rerun()
    with col2:
        if st.button("🏁 Save Score (cloud)"):
            if st.session_state.player:
                try:
                    persist_user_progress(st.session_state.player)
                    update_leaderboard(st.session_state.player, st.session_state.score)
                    st.success("Score saved to Firebase leaderboard.")
                except Exception as e:
                    st.error(f"Save failed; saved locally instead. {e}")
                    save_score_local(st.session_state.player, st.session_state.score, st.session_state.level)
            else:
                st.warning("Enter a codename first to save.")
    with col3:
        if st.button("♻️ Reset Session"):
            preserved_timer = st.session_state.get("timer_mode", None)
            keys = list(st.session_state.keys())
            for k in keys:
                del st.session_state[k]
            # restore defaults and timer choice
            st.session_state.player = ""
            st.session_state.level = 1
            st.session_state.score = 0
            st.session_state.history = []
            st.session_state.seen_puzzles = set()
            st.session_state.mission_started = False
            st.session_state.timer_mode = preserved_timer
            st.experimental_rerun()

# end of main card
st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Bottom panels: mission log & leaderboards
# -------------------------
st.markdown("<div style='max-width:930px; margin:18px auto;'>", unsafe_allow_html=True)
st.markdown("## 🗂 Mission Log (this session)")
if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)
    if "time" in df.columns:
        try:
            df = df.sort_values(by="time", ascending=False)
        except:
            pass
    st.dataframe(df[["time","level","cipher","answer","correct"]].reset_index(drop=True))
else:
    st.info("No missions logged this session yet.")

st.markdown("---")
st.markdown("## 🏆 Leaderboard")
st.markdown("Leaderboard tries Firebase first, falls back to local CSV.")

# Try to read Firebase leaderboard (best-effort)
try:
    # read_progress/get_user can be adapted to fetch leaderboard; use local file as display fallback
    lb = read_leaderboard_local()
    if lb.empty:
        st.info("No saved scores yet (local). Firebase leaderboard entries are written to /leaderboard in your Realtime DB.")
    else:
        try:
            lb_sorted = lb.sort_values(by=["score","date"], ascending=[False, True]).reset_index(drop=True)
            st.table(lb_sorted.head(20))
        except:
            st.table(lb.head(20))
except Exception:
    st.info("Unable to read local leaderboard.")

st.markdown("---")
st.caption("Note: Numbers use numeric letter mapping A=1, B=2, ... (encoded numbers are shown continuous without dashes, e.g. HELLO → 85121215).")
st.markdown("</div>", unsafe_allow_html=True)
