"""
Opportunity routes — manual creation (Gate 2) alongside the Discovery Agent pipeline
(Gate 4, see app/graphs/opportunity_pipeline.py) which creates Opportunities
automatically from raw text. Both paths share the same dedupe logic (app/core/dedupe.py)
and the same DB-level uniqueness guarantee (compound unique index on
(company_id, role_hash) — see app/models/opportunity.py).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.api.deps import get_current_user
from app.core.dedupe import role_hash as compute_role_hash
from app.models.opportunity import Company, Opportunity
from app.models.user import User
from app.schemas.opportunity import OpportunityCreate, OpportunityOut

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.post("", response_model=OpportunityOut, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    payload: OpportunityCreate,
    current_user: User = Depends(get_current_user),
):
    company = await Company.find_one(Company.name == payload.company_name)
    if company is None:
        company = Company(name=payload.company_name)
        await company.insert()

    hashed_role = compute_role_hash(payload.role)
    existing = await Opportunity.find_one(
        Opportunity.company_id == company.id,
        Opportunity.role_hash == hashed_role,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This opportunity already exists for this company (duplicate detected).",
        )

    opportunity = Opportunity(
        company_id=company.id,
        role=payload.role,
        role_hash=hashed_role,
        deadline=payload.deadline,
        source=payload.source,
    )
    try:
        await opportunity.insert()
    except DuplicateKeyError:
        # Backstop against a race between the check above and the insert — the compound
        # unique index is the actual source of truth, not the find_one() check.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This opportunity already exists for this company (duplicate detected).",
        )
    return opportunity


@router.get("", response_model=list[OpportunityOut])
async def list_opportunities(current_user: User = Depends(get_current_user)):
    return await Opportunity.find_all().sort(-Opportunity.created_at).to_list()
