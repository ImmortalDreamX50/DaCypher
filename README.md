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
  alphabet (A=1, B=2, ... Z=26), then transformed depending on the level:
  - **Levels 1–9:** alternating direct encoding and complement encoding
    (each number *n* becomes *27 − n*).
  - **Levels 10–19:** adds a third word pattern using complement plus a
    shift of −1.
  - **Levels 20–29:** same pattern but with a shift of −2.
  - **Levels 30+:** mixes complement with shifts of −2 and +1.
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

## Deploy on Streamlit Community Cloud

1. Create a free PostgreSQL database (e.g. [Supabase](https://supabase.com)
   free tier). Copy the **Connection string** (Session pooler) for your
   project.
2. Push this repository to GitHub.
3. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app
   from the repository and set the **Main file path** to `app.py`.
4. In the app's **Settings → Secrets**, add the connection string **and** the
   word bank (the JSON containing mission answers — keep it out of the repo):

   ```toml
   [postgres]
   database_url = "postgresql://postgres.PROJECT:password@aws-0-region.pooler.supabase.com:5432/postgres"

   [google]
   client_id = "your-google-oauth-client-id"
   client_secret = "your-google-oauth-client-secret"

   [wordbank]
   json = """
   {
     "1": [
       {
         "M": "Subject seen near embassy perimeter",
         "answer": "Espionage reconnaissance"
       }
     ]
   }
   """
   ```

   Replace with your actual values. Do not commit the connection string, client
   secret, or `wordbank.json` to the repository.
5. Deploy. Streamlit installs the Python packages listed in `requirements.txt`.

### Set up Google Sign-In (free)

1. Go to [Google Cloud Console](https://console.cloud.google.com) → create a
   project (or pick one) → **APIs & Services** → **OAuth consent screen**.
   Set it to **External**, add your email, and save. You can ignore the app
   verification step — unverified is fine for this size.
2. Under **Credentials → Create credentials → OAuth client ID**, choose
   **Web application**.
3. Add the redirect URI **exactly** as the app URL, e.g.
   `https://yourapp.streamlit.app` (and `http://localhost:8501` for local
   testing). Copy the client ID and secret into the `[google]` secret above.
4. On the OAuth consent screen, add `yourapp.streamlit.app`... your own email
   as a **test user** so only you can sign in until you publish the app.

The `accounts`, `users`, and `leaderboard` tables are created automatically on
first run.

### How secrets work in this app

Streamlit Community Cloud requires a **public** GitHub repo on its free tier, so
anything you commit is publicly readable. Nothing sensitive is committed:

- **Postgres** connection string and **Google** OAuth secret → `st.secrets`
  (stored encrypted in the Streamlit dashboard, never in the repo).
- **wordbank.json** (contains the mission answers) → also in `st.secrets`
  under `[wordbank] json`. The file is listed in `.gitignore`, so it stays
  local only. The app reads from `st.secrets` first and falls back to the
  local file during development.

To publish the app you only need to commit the code; the secrets and word bank
are pasted into the Streamlit **Settings → Secrets** page. To generate the
`[wordbank]` value from your local file:

```bash
python -c "import json, pathlib; print(json.dumps(json.loads(pathlib.Path('wordbank.json').read_text())))"
```

...then paste the output inside the `"""` block.

## Run locally

Install dependencies with `pip install -r requirements.txt`, then run
`streamlit run app.py`. Provide the database connection string and Google OAuth
values through Streamlit secrets (`.streamlit/secrets.toml`) or, for Postgres,
the `DATABASE_URL` environment variable:

```toml
[postgres]
database_url = "postgresql://..."

[google]
client_id = "your-google-oauth-client-id.apps.googleusercontent.com"
client_secret = "your-google-oauth-client-secret"
```

For local development the app reads `wordbank.json` directly from the project
folder (it is gitignored), so there is no need to copy it into secrets locally.
