import hmac
import os
import re
import secrets
import sqlite3
from functools import wraps

from flask import (Flask, abort, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from core.engine import respond
from db import close_db, get_db, init_db
from ml.predict import EmotionClassifier

MAX_LEN = 1000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")

# +1 = positive feeling, -1 = low feeling, 0 = neutral. Used for the mood trend chart.
VALENCE = {"joy": 1, "love": 1, "surprise": 0,
           "sadness": -1, "anger": -1, "fear": -1, "distress": -1}


def create_app(classifier=None, database=None):
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
    here = os.path.dirname(os.path.abspath(__file__))
    app.config["DATABASE"] = database or os.environ.get("DATABASE") or os.path.join(here, "app.db")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    clf = classifier or EmotionClassifier()

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    # ---------- helpers ----------
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    def check_csrf():
        """Reject form posts and state-changing calls that don't carry our secret token."""
        sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf", "")
        if not sent or not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
            abort(400, "Invalid or missing security token. Please reload the page.")

    @app.context_processor
    def inject_globals():
        return {"username": session.get("username"), "csrf_token": csrf_token}

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify(error="Please log in."), 401
                return redirect(url_for("login"))
            return fn(*args, **kwargs)
        return wrapper

    def start_session(user_id, name):
        session.clear()  # also prevents session fixation
        session["user_id"] = user_id
        session["username"] = name
        session["csrf"] = secrets.token_hex(16)

    def log_mood(result):
        """Save emotion, intensity and risk for signed-in users. Message text is never saved."""
        user_id = session.get("user_id")
        if not user_id:
            return
        if result["risk"] == "high":
            emotion = "distress"
        elif result["emotion"]:
            emotion = result["emotion"]
        else:
            return  # greetings and "tell me more" replies are not mood check-ins
        db = get_db()
        db.execute(
            "INSERT INTO mood_logs (user_id, emotion, intensity, confidence, risk) VALUES (?, ?, ?, ?, ?)",
            (user_id, emotion, result["intensity"], result["confidence"], result["risk"]))
        db.commit()

    # ---------- pages ----------
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        error, name = None, ""
        if request.method == "POST":
            check_csrf()
            name = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if not USERNAME_RE.match(name):
                error = "Username must be 3-30 letters, numbers or underscores."
            elif not 8 <= len(password) <= 128:
                error = "Password must be 8 to 128 characters."
            else:
                db = get_db()
                try:
                    cur = db.execute("INSERT INTO users (username, pw_hash) VALUES (?, ?)",
                                     (name, generate_password_hash(password)))
                    db.commit()
                except sqlite3.IntegrityError:
                    error = "That username is already taken."
                else:
                    start_session(cur.lastrowid, name)
                    return redirect(url_for("index"))
        return render_template("auth.html", mode="register", error=error, name=name)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error, name = None, ""
        if request.method == "POST":
            check_csrf()
            name = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            row = get_db().execute(
                "SELECT id, username, pw_hash FROM users WHERE username = ?", (name,)).fetchone()
            if row and check_password_hash(row["pw_hash"], password):
                start_session(row["id"], row["username"])
                return redirect(url_for("index"))
            error = "Incorrect username or password."  # same message either way, on purpose
        return render_template("auth.html", mode="login", error=error, name=name)

    @app.post("/logout")
    def logout():
        check_csrf()
        session.clear()
        return redirect(url_for("index"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    # ---------- chat API ----------
    @app.post("/api/chat")
    def chat():
        data = request.get_json(silent=True)
        text = data.get("message") if isinstance(data, dict) else None
        if not isinstance(text, str) or not text.strip():
            return jsonify(error="Please send a non-empty 'message'."), 400
        text = text.strip()
        if len(text) > MAX_LEN:
            return jsonify(error=f"Message is too long (max {MAX_LEN} characters)."), 400

        # Only emotion labels are kept in the session, never the message text
        history = list(session.get("history", []))
        result = respond(text, clf, history)
        session["history"] = history
        log_mood(result)
        return jsonify(result)

    @app.post("/api/reset")
    def reset():
        session.pop("history", None)
        return jsonify(ok=True)

    # ---------- mood API ----------
    @app.get("/api/mood")
    @login_required
    def mood():
        days = max(1, min(request.args.get("days", 30, type=int), 365))
        tz = max(-840, min(request.args.get("tz", 0, type=int), 840))  # minutes from UTC
        rows = get_db().execute(
            "SELECT emotion, intensity, created, date(created, ?) AS day FROM mood_logs "
            "WHERE user_id = ? AND created >= datetime('now', ?) ORDER BY created",
            (f"{tz:+d} minutes", session["user_id"], f"-{days} days")).fetchall()
        return jsonify(summarize(rows))

    @app.delete("/api/mood")
    @login_required
    def delete_mood():
        check_csrf()
        db = get_db()
        db.execute("DELETE FROM mood_logs WHERE user_id = ?", (session["user_id"],))
        db.commit()
        return jsonify(ok=True)

    return app


def summarize(rows):
    """Turn raw check-ins into a daily mood trend, emotion counts and a few totals."""
    per_day, counts = {}, {}
    for r in rows:
        score = VALENCE.get(r["emotion"], 0) * r["intensity"]
        per_day.setdefault(r["day"], []).append(score)
        counts[r["emotion"]] = counts.get(r["emotion"], 0) + 1
    daily = [{"day": d, "mood": round(sum(v) / len(v), 2), "n": len(v)}
             for d, v in sorted(per_day.items())]
    return {
        "daily": daily,
        "counts": counts,
        "total": len(rows),
        "top": max(counts, key=counts.get) if counts else None,
        "last": rows[-1]["created"] if rows else None,
    }


if __name__ == "__main__":
    create_app().run(debug=True)