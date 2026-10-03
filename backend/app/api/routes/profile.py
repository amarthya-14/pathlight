"""
Profile routes — minimal upsert/get, added at Gate 4 because the Eligibility Agent is
otherwise untestable through the API layer: without a way to set CGPA/branch, there is no
real path for a user to ever be anything but "profile missing" (see the UNCERTAIN
fallback in app/graphs/opportunity_pipeline.py).
"""
from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.models.user import Profile, User
from app.schemas.profile import ProfileOut, ProfileUpsert

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.put("", response_model=ProfileOut, status_code=status.HTTP_200_OK)
async def upsert_profile(payload: ProfileUpsert, current_user: User = Depends(get_current_user)):
    data = payload.model_dump()
    data["target_roles"] = _clean_list(payload.target_roles)
    data["preferred_locations"] = _clean_list(payload.preferred_locations)
    if payload.github_username:
        # People paste the whole URL; the GitHub MCP lookup needs just the username.
        data["github_username"] = payload.github_username.strip().rstrip("/").split("/")[-1].lstrip("@") or None
    profile = await Profile.find_one(Profile.user_id == current_user.id)
    if profile is None:
        profile = Profile(user_id=current_user.id, **data)
        await profile.insert()
    else:
        for key, value in data.items():
            setattr(profile, key, value)
        await profile.save()
    return profile


def _clean_list(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))[:8]


@router.get("", response_model=ProfileOut)
async def get_profile(current_user: User = Depends(get_current_user)):
    profile = await Profile.find_one(Profile.user_id == current_user.id)
    if profile is None:
        # Return id=None rather than a fake ID — "no profile yet" is a normal, expected
        # state (see the eligibility pipeline's UNCERTAIN handling), not an error.
        return ProfileOut(id=None, user_id=current_user.id, cgpa=None, branch=None)
    return profile
