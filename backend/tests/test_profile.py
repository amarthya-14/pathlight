"""Profile upsert/get tests — added at Gate 4 alongside the Eligibility Agent that needs it."""


def _auth_headers(client, email="profile-user@example.com", password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/api/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


def test_profile_defaults_to_none_before_creation(client):
    headers = _auth_headers(client)
    resp = client.get("/api/profile", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] is None
    assert body["cgpa"] is None


def test_profile_upsert_and_get(client):
    headers = _auth_headers(client, email="profile-user2@example.com")

    resp = client.put("/api/profile", json={"cgpa": 8.2, "branch": "ECE"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["cgpa"] == 8.2

    resp2 = client.get("/api/profile", headers=headers)
    assert resp2.json()["cgpa"] == 8.2
    assert resp2.json()["branch"] == "ECE"

    # upsert again should update, not duplicate
    client.put("/api/profile", json={"cgpa": 9.1, "branch": "ECE"}, headers=headers)
    resp3 = client.get("/api/profile", headers=headers)
    assert resp3.json()["cgpa"] == 9.1


def test_profile_requires_auth(client):
    resp = client.get("/api/profile")
    assert resp.status_code == 401
