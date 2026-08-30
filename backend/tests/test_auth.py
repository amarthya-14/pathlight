def test_register_and_login(client):
    register_resp = client.post(
        "/api/auth/register",
        json={"email": "student@example.com", "password": "supersecret", "full_name": "Ananya"},
    )
    assert register_resp.status_code == 201
    assert register_resp.json()["email"] == "student@example.com"

    # Duplicate email should be rejected
    dup_resp = client.post(
        "/api/auth/register",
        json={"email": "student@example.com", "password": "anotherpass"},
    )
    assert dup_resp.status_code == 409

    login_resp = client.post(
        "/api/auth/login",
        data={"username": "student@example.com", "password": "supersecret"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "wrong@example.com", "password": "correctpass"},
    )
    resp = client.post(
        "/api/auth/login",
        data={"username": "wrong@example.com", "password": "incorrectpass"},
    )
    assert resp.status_code == 401
