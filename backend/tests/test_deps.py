"""get_current_user (app/api/deps.py) auth-failure branches — added at Gate 9 to cover
the security-relevant paths coverage showed as untested: a token whose subject isn't a
valid ObjectId, and a token for a user that no longer exists."""
from beanie import PydanticObjectId

from app.core.security import create_access_token


def test_protected_route_rejects_garbage_token(client):
    resp = client.get("/api/profile", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401


def test_protected_route_rejects_token_with_non_objectid_subject(client):
    token = create_access_token(subject="not-an-object-id")
    resp = client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_protected_route_rejects_token_for_deleted_user(client):
    token = create_access_token(subject=str(PydanticObjectId()))
    resp = client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
