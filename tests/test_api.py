import pytest

from app import create_app


class FakeClassifier:
    """Stands in for the real model so the tests are fast and predictable."""
    def predict(self, text):
        emotion = "sadness" if "sad" in text.lower() else "joy"
        return {"emotion": emotion, "confidence": 0.95, "top": []}


@pytest.fixture()
def client(tmp_path):
    app = create_app(classifier=FakeClassifier(), database=str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    return app.test_client()


def post(client, message):
    return client.post("/api/chat", json={"message": message})


def test_health(client):
    assert client.get("/health").get_json()["status"] == "ok"


def test_index_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"How are you feeling today?" in response.data


def test_static_files_are_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/pages.css").status_code == 200
    assert client.get("/static/dashboard.js").status_code == 200


def test_empty_message_is_rejected(client):
    assert post(client, "   ").status_code == 400


def test_missing_message_is_rejected(client):
    assert client.post("/api/chat", json={}).status_code == 400


def test_too_long_message_is_rejected(client):
    assert post(client, "a" * 1001).status_code == 400


def test_normal_message(client):
    data = post(client, "i am so happy today").get_json()
    assert data["emotion"] == "joy"
    assert data["risk"] == "none"
    assert data["reply"]


def test_crisis_message_overrides_the_model(client):
    data = post(client, "i want to end my life").get_json()
    assert data["risk"] == "high"
    assert data["helplines"]


def test_memory_persists_within_a_session(client):
    post(client, "i feel sad")
    data = post(client, "i am so happy now").get_json()
    assert "lighter" in data["reply"]


def test_reset_clears_memory(client):
    post(client, "i feel sad")
    client.post("/api/reset")
    data = post(client, "i am so happy now").get_json()
    assert "lighter" not in data["reply"]