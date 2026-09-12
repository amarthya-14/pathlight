"""
Opportunity ingestion route — the first real caller of both the LangGraph pipeline
(app/graphs/opportunity_pipeline.py) and the Filesystem MCP tool (app/mcp/filesystem_client.py)
outside of tests. Accepts either raw text directly or a reference to a previously
uploaded Document, read via MCP rather than the API layer reaching into disk itself.
"""
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.graphs.opportunity_pipeline import run_opportunity_pipeline
from app.mcp.filesystem_client import mcp_read_document
from app.models.document import Document
from app.models.opportunity import Company, Opportunity
from app.models.user import User
from app.schemas.ingest import IngestRequest, IngestResponse

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest_opportunity(payload: IngestRequest, current_user: User = Depends(get_current_user)):
    if not payload.raw_text and not payload.document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either raw_text or document_id.",
        )
    if payload.raw_text and payload.document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide only one of raw_text or document_id, not both.",
        )

    if payload.document_id:
        try:
            oid = PydanticObjectId(payload.document_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        document = await Document.get(oid)
        if document is None or document.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        # Read via the Filesystem MCP tool, not by touching disk directly here — this is
        # the standardized interface every agent (and, later, every MCP tool) uses.
        raw_text = await mcp_read_document(str(current_user.id), document.storage_filename)
        source = f"document:{document.doc_type.value}"
    else:
        raw_text = payload.raw_text
        source = payload.source

    result = await run_opportunity_pipeline(raw_text, source, str(current_user.id))

    if result.get("needs_human_review"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not process this opportunity automatically: {result.get('error')}",
        )

    opportunity = await Opportunity.get(PydanticObjectId(result["opportunity_id"]))
    company = await Company.get(opportunity.company_id)
    extraction = result["extraction"]

    return IngestResponse(
        opportunity_id=result["opportunity_id"],
        application_id=result["application_id"],
        company_name=company.name,
        role=extraction.role,
        eligibility=result.get("eligibility"),
        skill_gap=result.get("skill_gap"),
        skill_gap_note=result.get("skill_gap_note"),
        needs_human_review=False,
    )
