import sqlite3

import pytest

from app import create_app


class FakeClassifier:
    def predict(self, text):
        emotion = "sadness" if "sad" in text.lower() else "joy"
        return {"emotion": emotion, "confidence": 0.95, "top": []}


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture()
def app(db_path):
    application = create_app(classifier=FakeClassifier(), database=db_path)
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def token(client):
    """Load a page so the session gets a CSRF token, then read it."""
    client.get("/login")
    with client.session_transaction() as s:
        return s["csrf"]


def register(client, name="tester", password="longpassword1"):
    return client.post("/register", data={"username": name, "password": password, "csrf": token(client)})


def chat(client, text):
    return client.post("/api/chat", json={"message": text})


def rows(db_path, sql, args=()):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


# ---------- registration and login ----------
def test_register_logs_you_in(client):
    r = register(client)
    assert r.status_code == 302
    assert b"tester" in client.get("/").data


def test_password_is_stored_hashed(client, db_path):
    register(client, password="longpassword1")
    stored = rows(db_path, "SELECT pw_hash FROM users")[0][0]
    assert stored != "longpassword1"
    assert "longpassword1" not in stored


def test_username_taken_ignores_case(client):
    register(client, "Alice")
    other = client.application.test_client()
    r = other.post("/register", data={"username": "alice", "password": "longpassword1", "csrf": token(other)})
    assert r.status_code == 200
    assert b"already taken" in r.data


def test_short_password_rejected(client):
    r = register(client, password="short")
    assert r.status_code == 200
    assert b"8 to 128" in r.data


def test_bad_username_rejected(client):
    r = register(client, name="bad name!")
    assert b"3-30 letters" in r.data


def test_missing_csrf_token_is_rejected(client):
    r = client.post("/register", data={"username": "tester", "password": "longpassword1"})
    assert r.status_code == 400


def test_wrong_password_fails(client):
    register(client)
    other = client.application.test_client()
    r = other.post("/login", data={"username": "tester", "password": "wrongpassword", "csrf": token(other)})
    assert r.status_code == 200
    assert b"Incorrect username or password" in r.data
    assert other.get("/dashboard").status_code == 302  # still logged out


def test_login_and_logout(client):
    register(client)
    client.post("/logout", data={"csrf": token(client)})
    assert client.get("/dashboard").status_code == 302
    r = client.post("/login", data={"username": "tester", "password": "longpassword1", "csrf": token(client)})
    assert r.status_code == 302
    assert client.get("/dashboard").status_code == 200


def test_dashboard_requires_login(client):
    r = client.get("/dashboard")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_mood_api_requires_login(client):
    assert client.get("/api/mood").status_code == 401


# ---------- mood logging ----------
def test_guest_chat_is_not_logged(client, db_path):
    chat(client, "i feel sad")
    assert rows(db_path, "SELECT COUNT(*) FROM mood_logs")[0][0] == 0


def test_signed_in_chat_is_logged_without_message_text(client, db_path):
    register(client)
    chat(client, "i feel sad about my secret problem")
    saved = rows(db_path, "SELECT emotion, intensity, risk FROM mood_logs")
    assert len(saved) == 1
    assert saved[0][0] == "sadness"
    columns = [c[1] for c in rows(db_path, "PRAGMA table_info(mood_logs)")]
    assert not any(name in columns for name in ("message", "text", "content"))


def test_crisis_is_logged_as_distress(client, db_path):
    register(client)
    chat(client, "i want to end my life")
    saved = rows(db_path, "SELECT emotion, risk FROM mood_logs")
    assert saved == [("distress", "high")]


def test_small_talk_is_not_logged(client, db_path):
    register(client)
    chat(client, "hello")
    assert rows(db_path, "SELECT COUNT(*) FROM mood_logs")[0][0] == 0


def test_mood_summary(client):
    register(client)
    chat(client, "i feel sad")
    chat(client, "i feel sad")
    chat(client, "i am so happy")
    data = client.get("/api/mood?days=30&tz=330").get_json()
    assert data["total"] == 3
    assert data["counts"] == {"sadness": 2, "joy": 1}
    assert data["top"] == "sadness"
    assert len(data["daily"]) == 1
    assert data["daily"][0]["n"] == 3


def test_users_only_see_their_own_data(client, app):
    register(client, "alice")
    chat(client, "i feel sad")
    bob = app.test_client()
    register(bob, "bobby")
    assert bob.get("/api/mood").get_json()["total"] == 0
    assert client.get("/api/mood").get_json()["total"] == 1


def test_delete_needs_csrf_token(client):
    register(client)
    chat(client, "i feel sad")
    assert client.delete("/api/mood").status_code == 400
    assert client.get("/api/mood").get_json()["total"] == 1


def test_delete_my_data(client):
    register(client)
    chat(client, "i feel sad")
    r = client.delete("/api/mood", headers={"X-CSRF-Token": token(client)})
    assert r.status_code == 200
    assert client.get("/api/mood").get_json()["total"] == 0