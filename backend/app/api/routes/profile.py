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
    profile = await Profile.find_one(Profile.user_id == current_user.id)
    if profile is None:
        profile = Profile(user_id=current_user.id, cgpa=payload.cgpa, branch=payload.branch)
        await profile.insert()
    else:
        profile.cgpa = payload.cgpa
        profile.branch = payload.branch
        await profile.save()
    return profile


@router.get("", response_model=ProfileOut)
async def get_profile(current_user: User = Depends(get_current_user)):
    profile = await Profile.find_one(Profile.user_id == current_user.id)
    if profile is None:
        # Return id=None rather than a fake ID — "no profile yet" is a normal, expected
        # state (see the eligibility pipeline's UNCERTAIN handling), not an error.
        return ProfileOut(id=None, user_id=current_user.id, cgpa=None, branch=None)
    return profile
