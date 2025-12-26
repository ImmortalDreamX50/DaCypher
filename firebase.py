import os
import json
import firebase_admin
from firebase_admin import credentials, db
import uuid

# =========================
# FIREBASE INITIALIZATION
# =========================

if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")

    if not firebase_json:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT env variable not set")

    cred_dict = json.loads(firebase_json)
    cred = credentials.Certificate(cred_dict)

    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://cipher-d2ffa-default-rtdb.firebaseio.com/"
    })

# ---------- DATABASE FUNCTIONS ----------

def create_user(uid, username):
    """Create user account if not exists"""
    ref = db.reference(f"users/{uid}")
    if ref.get() is None:
        ref.set({
            "username": username,
            "score": 0,
            "level": 1,
            "uses_hint": 0
        })
        # Update leaderboard with initial score 0
        update_leaderboard(username, 0)

def get_user(uid):
    return db.reference(f"users/{uid}").get()

def update_score(uid, username, new_score):
    """Update user score and leaderboard"""
    db.reference(f"users/{uid}/score").set(new_score)
    update_leaderboard(username, new_score)  # Use username for leaderboard

def update_level(uid, new_level):
    db.reference(f"users/{uid}/level").set(new_level)

def increment_hint_usage(uid):
    ref = db.reference(f"users/{uid}/uses_hint")
    current = ref.get() or 0
    ref.set(current + 1)

def update_leaderboard(username, score):
    """Leaderboard sorted by score"""
    db.reference("leaderboard").update({username: score})

def save_progress(uid, username, level, score):
    """Save full user progress"""
    ref = db.reference(f"users/{uid}")
    ref.update({
        "username": username,
        "level": level,
        "score": score
    })
    update_leaderboard(username, score)

def get_progress(uid):
    return db.reference(f"users/{uid}").get()

# ---------- EXAMPLE USAGE ----------

if __name__ == "__main__":
    uid = str(uuid.uuid4())
    username = "Lavhelani"
    
    create_user(uid, username)
    update_score(uid, username, 50)
    increment_hint_usage(uid)
    
    print(get_progress(uid))
