def _auth_headers(client, email="opp-user@example.com", password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/api/auth/login", data={"username": email, "password": password})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_opportunity(client):
    headers = _auth_headers(client)

    create_resp = client.post(
        "/api/opportunities",
        json={"company_name": "Acme Corp", "role": "Backend Intern", "source": "manual"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["role"] == "Backend Intern"

    list_resp = client.get("/api/opportunities", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_duplicate_opportunity_rejected(client):
    headers = _auth_headers(client)
    payload = {"company_name": "Acme Corp", "role": "Backend Intern", "source": "manual"}

    first = client.post("/api/opportunities", json=payload, headers=headers)
    assert first.status_code == 201

    duplicate = client.post("/api/opportunities", json=payload, headers=headers)
    assert duplicate.status_code == 409


def test_opportunities_require_auth(client):
    resp = client.get("/api/opportunities")
    assert resp.status_code == 401


async def test_dedupe_enforced_at_db_level_not_just_app_check(client):
    """
    Regression test: the (company_id, role_hash) unique index must itself reject a
    duplicate insert, not just the find_one() check in the route handler. Without this,
    a race between two concurrent requests could both pass the find_one() check and both
    insert — the DB constraint is what actually prevents that, and this test would only
    catch a regression if it talks to the model layer directly, bypassing the route.
    """
    from pymongo.errors import DuplicateKeyError

    from app.models.opportunity import Company, Opportunity

    company = Company(name="DirectTestCo")
    await company.insert()

    first = Opportunity(company_id=company.id, role="Engineer", role_hash="same-hash")
    await first.insert()

    second = Opportunity(company_id=company.id, role="Engineer (different title, same hash)", role_hash="same-hash")
    try:
        await second.insert()
        assert False, "expected DuplicateKeyError — unique index is not being enforced"
    except DuplicateKeyError:
        pass
