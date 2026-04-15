"""
Shared Pydantic models used as structured outputs across the pipeline.
Each Task's output_pydantic points to one of these — ensures agents
pass clean, typed data to each other rather than free-form strings.
"""

from pydantic import BaseModel, Field
from typing import Literal


# ---------------------------------------------------------------------------
# Hunter output
# ---------------------------------------------------------------------------

class DiscoveredProfile(BaseModel):
    id:           str
    name:         str
    title:        str
    company:      str
    linkedin_url: str
    email:        str
    seniority:    str
    industry:     str
    company_size: str
    tier1_signals: list[str] = Field(
        description="High-confidence signals: matching skills, job experience, certifications"
    )
    tier2_signals: list[str] = Field(
        description="Moderate signals: posts with relevant hashtags, migration mentions"
    )


class HunterOutput(BaseModel):
    profiles:            list[DiscoveredProfile]
    total_fetched:       int
    total_with_signals:  int


# ---------------------------------------------------------------------------
# Qualifier output
# ---------------------------------------------------------------------------

class QualifiedLead(BaseModel):
    id:                   str
    name:                 str
    title:                str
    company:              str
    linkedin_url:         str
    email:                str
    seniority:            str
    industry:             str
    company_size:         str
    tier1_signals:        list[str]
    tier2_signals:        list[str]
    status:               Literal["QUALIFIED", "BLOCKED", "SKIPPED"]
    score:                int = Field(ge=0, le=100)
    qualification_notes:  str


class QualifierOutput(BaseModel):
    leads:      list[QualifiedLead]
    qualified:  int
    blocked:    int
    skipped:    int


# ---------------------------------------------------------------------------
# Copywriter output
# ---------------------------------------------------------------------------

class LeadMessages(BaseModel):
    lead_id:        str
    lead_name:      str
    linkedin_invite: str = Field(description="Max 300 characters")
    email_subject:  str
    email_body:     str


class CopywriterOutput(BaseModel):
    messages: list[LeadMessages]


# ---------------------------------------------------------------------------
# Evaluator output
# ---------------------------------------------------------------------------

class EvaluatedMessage(BaseModel):
    lead_id:               str
    lead_name:             str
    linkedin_invite:       str
    linkedin_score:        int = Field(ge=0, le=100)
    linkedin_status:       Literal["APPROVED", "REJECTED"]
    linkedin_notes:        str
    email_subject:         str
    email_body:            str
    email_score:           int = Field(ge=0, le=100)
    email_status:          Literal["APPROVED", "REJECTED"]
    email_notes:           str


class EvaluatorOutput(BaseModel):
    messages:  list[EvaluatedMessage]
    approved:  int
    rejected:  int
