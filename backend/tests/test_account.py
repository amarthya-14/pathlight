"""Data export and account deletion."""
from app.models.application import Application
from app.models.document import Document
from app.models.user import Profile, User

RESUME = "Asha Rao\nasha@example.com\nSkills\nPython, Django"


def _setup(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123", "full_name": "Asha Rao"})
    token = client.post("/api/auth/login", data={"username": email, "password": "testpass123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put("/api/profile", json={"cgpa": 8.0, "branch": "CSE"}, headers=headers)
    client.post("/api/documents/paste", json={"doc_type": "resume", "title": "Resume", "text": RESUME}, headers=headers)
    return headers


def test_export_contains_my_data_but_no_secrets(client):
    headers = _setup(client, "export@example.com")
    data = client.get("/api/account/export", headers=headers).json()
    assert data["user"]["email"] == "export@example.com"
    assert "hashed_password" not in data["user"]
    assert data["profile"][0]["cgpa"] == 8.0
    assert data["documents"][0]["extracted_text"] == RESUME
    assert "content" not in data["documents"][0]


async def test_delete_requires_confirmation_then_erases_everything(client):
    headers = _setup(client, "erase@example.com")
    assert client.request("DELETE", "/api/account", json={"confirm": "nope"}, headers=headers).status_code == 400
    assert client.request("DELETE", "/api/account", json={"confirm": "DELETE", "password": "wrong"}, headers=headers).status_code == 400

    assert client.request("DELETE", "/api/account", json={"confirm": "DELETE"}, headers=headers).status_code == 204

    assert await User.find_one(User.email == "erase@example.com") is None
    assert await Profile.count() == 0
    assert await Document.count() == 0
    assert await Application.count() == 0
    assert client.get("/api/auth/me", headers=headers).status_code == 401
