# DaCypher

DaCypher (Agency Intel Ops) is a Streamlit cipher-missions game backed by a free
PostgreSQL database (e.g. Supabase free tier or self-hosted).

## What the Game Does

You are an intelligence agent assigned to a decryption terminal. Each mission
presents an **intercepted transmission** — a phrase encoded as a stream of
numbers using one of several cipher schemes. Your job is to decode it and
submit the original phrase.

- **Sign in** with email + password (registered accounts) or with your Google
  account (free Google OAuth).
- **Choose a codename** after the first login; it is the callsign shown on the
  leaderboard. Progress (level, score, hint usage) persists per email between
  sessions.
- **Decode the transmission.** Each letter is converted to its position in the
  alphabet (A=1, B=2, ... Z=26), then transformed using a cipher scheme that
  grows more complex as your level increases.
- **Score points** for correct answers: `5 + level / 2` points per success.
  A wrong answer costs 2 points (score never drops below 0) and the mission
  is marked as compromised.
- **Level up** on each correct answer; a new, harder mission is generated
  from the word bank.
- **Use hints** when stuck (see below). Each hint use is counted and saved.
- **Restart a mission** to get a different question at the same level — you
  cannot skip levels.
- **Mission Debrief** shows a session log of every attempt with its status
  (SUCCESS / FAILED), the cipher, and your answer.
- **Leaderboard** score is updated in PostgreSQL on every correct answer.

## Hint Section — What is M I P B E?

When you press **💡 Get Hint** during a mission, you receive five clues
labelled **M, I, P, B, E**. Each letter stands for a category of intel that
helps you deduce the intercepted phrase:

| Letter | Meaning            | Description                                                                 |
| ------ | ------------------ | --------------------------------------------------------------------------- |
| **M**  | **Mission context** | The overall situation or objective — what the mission is about.             |
| **I**  | **Intercepted detail** | A specific detail captured from the intercepted communication.              |
| **P**  | **Physical proof** | Tangible evidence recovered (devices, documents, items found on-site).      |
| **B**  | **Backstory**      | Background or cover story related to the subject or event.                  |
| **E**  | **Evidence**       | Verified, analyzed evidence such as logs, traces, or records confirming the facts. |

Together the five clues narrow down the decoded phrase. If no mission is
active, the hint button simply displays the meanings of M, I, P, B, E.

## Project Structure

- `app.py` — Streamlit UI: login (email/password + Google), codename setup,
  missions, hints, scoring, debrief.
- `Cipher.py` — Cipher engine (encode/decode for each level band).
- `database.py` — PostgreSQL helpers (accounts, users, progress, leaderboard).
- `wordbank.json` — Missions per level, each with M/I/P/B/E clues and the
  `answer`.
