"""
Account routes — the student's control over their own data (India's DPDP Act 2023:
access and erasure on request; also what Google's OAuth review expects of any app that
holds Gmail tokens).

- GET    /api/account/export : everything Pathlight stores about the user, as JSON.
- DELETE /api/account        : erases it all — Gmail access is revoked with Google first,
                               then every user-owned record, uploaded file and resume
                               embedding. Postings (Opportunity/Company) are shared, not
                               personal, and stay.
"""
import shutil

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.security import verify_password
from app.core.usage import UsageCounter
from app.integrations.google_oauth import revoke_and_delete
from app.mcp.sandbox import user_dir
from app.models.agent_execution import AgentExecution
from app.models.application import Application
from app.models.calendar_event import CalendarEvent
from app.models.document import Document
from app.models.integration import Integration
from app.models.preparation import PreparationPlan
from app.models.tailored_resume import TailoredResume
from app.models.user import Profile, User
from app.retrieval.vector_store import get_resume_chunks_collection

router = APIRouter(prefix="/api/account", tags=["account"])


class DeleteAccountRequest(BaseModel):
    # Typed confirmation, not a password: Google-created accounts don't know theirs.
    confirm: str
    password: str | None = None


@router.get("/export")
async def export_account(current_user: User = Depends(get_current_user)):
    uid = current_user.id

    def dump(docs, exclude: set[str] = frozenset()):
        return [d.model_dump(mode="json", exclude=set(exclude) | {"revision_id"}) for d in docs]

    data = {
        "user": current_user.model_dump(mode="json", exclude={"hashed_password", "revision_id"}),
        "profile": dump(await Profile.find(Profile.user_id == uid).to_list()),
        "documents": dump(await Document.find(Document.owner_id == uid).to_list(), {"content"}),
        "applications": dump(await Application.find(Application.user_id == uid).to_list()),
        "tailored_resumes": dump(await TailoredResume.find(TailoredResume.user_id == uid).to_list()),
        "preparation_plans": dump(await PreparationPlan.find(PreparationPlan.user_id == uid).to_list()),
        "calendar_events": dump(await CalendarEvent.find(CalendarEvent.user_id == uid).to_list()),
        # Tokens are secrets, never exported — only that a connection exists.
        "integrations": dump(
            await Integration.find(Integration.user_id == uid).to_list(),
            {"encrypted_access_token", "encrypted_refresh_token", "processed_message_ids"},
        ),
    }
    return JSONResponse(data, headers={"Content-Disposition": 'attachment; filename="pathlight-data.json"'})


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(payload: DeleteAccountRequest, current_user: User = Depends(get_current_user)):
    if payload.confirm.strip().upper() != "DELETE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Type DELETE to confirm.')
    if payload.password is not None and not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That password is incorrect.")

    uid = current_user.id
    try:
        await revoke_and_delete(str(uid))  # revokes the Google grant, then drops tokens
    except Exception:
        pass  # revocation is best-effort; the encrypted tokens are deleted below regardless
    try:
        get_resume_chunks_collection().delete(where={"user_id": str(uid)})
    except Exception:
        pass
    for model, field in (
        (TailoredResume, TailoredResume.user_id),
        (PreparationPlan, PreparationPlan.user_id),
        (CalendarEvent, CalendarEvent.user_id),
        (Application, Application.user_id),
        (AgentExecution, AgentExecution.user_id),
        (Integration, Integration.user_id),
        (Document, Document.owner_id),
        (Profile, Profile.user_id),
        (UsageCounter, UsageCounter.user_id),
    ):
        await model.find(field == uid).delete()
    shutil.rmtree(user_dir(str(uid)), ignore_errors=True)
    await current_user.delete()
