"""
Shared dedupe-key logic. Used by both the manual Opportunity creation route
(app/api/routes/opportunities.py) and the Discovery Agent pipeline
(app/agents/discovery.py, app/graphs/opportunity_pipeline.py), so there is exactly one
definition of "what makes two opportunities the same" rather than two that could drift.
"""
import hashlib


def role_hash(role: str) -> str:
    """Normalize + hash the role string for dedupe matching. Deliberately simple for now
    — see docs/ARCHITECTURE.md on duplicate detection for the fuller strategy
    (embeddings-assisted, catching near-duplicate titles) planned for a later gate."""
    return hashlib.sha256(role.strip().lower().encode()).hexdigest()
