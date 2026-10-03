"""
TailoredResume — Gate 10. The Resume Tailor Agent's output (app/agents/resume_tailor.py)
for one Application: a reworded/reordered version of the user's base resume aimed at that
opportunity, plus the cover note that would accompany it.

One per application (unique index), regenerated in place on re-run — same pattern and
reasoning as PreparationPlan (app/models/preparation.py): independently regenerated and
fetched via its own route, so not embedded in Application. No server-side diff is stored;
the frontend diffs tailored_text against the base Document's extracted_text at render
time (docs/AUTONOMOUS_APPLICATIONS.md §4).
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


class TailoredResume(Document):
    application_id: Indexed(PydanticObjectId, unique=True)
    user_id: Indexed(PydanticObjectId)
    base_document_id: PydanticObjectId
    tailored_text: str
    cover_note: str
    changes_summary: list[str] = Field(default_factory=list)
    skills_emphasized: list[str] = Field(default_factory=list)
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    # Deterministic ATS score of tailored_text against the posting (app/core/ats.py) —
    # AtsReport.as_dict(): score, breakdown, matched/fixable/missing keywords, blocked_points.
    ats: dict | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "tailored_resumes"
