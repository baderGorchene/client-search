"""Pydantic v2 data models and validation schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeadStatus(str, Enum):
    """Lifecycle status states for client leads."""

    PENDING_LEAD_REVIEW = "PENDING_LEAD_REVIEW"
    LEAD_REJECTED = "LEAD_REJECTED"
    DRAFT_GENERATED = "DRAFT_GENERATED"
    DRAFT_REJECTED = "DRAFT_REJECTED"
    EMAIL_SENT = "EMAIL_SENT"
    REPLIED_INTERESTED = "REPLIED_INTERESTED"
    REPLIED_NOT_INTERESTED = "REPLIED_NOT_INTERESTED"


class LeadEvaluation(BaseModel):
    """Structured evaluation output produced by LLM for a discovered prospect."""

    company_name: str = Field(..., description="Target company or organization name")
    website_url: str = Field(..., description="Official website URL")
    decision_maker_name: str = Field(default="", description="Identified founder, owner, or executive name")
    decision_maker_title: str = Field(default="", description="Title/role of the decision maker")
    decision_maker_email: str = Field(default="", description="Resolved or verified email address")
    fit_score: int = Field(..., ge=1, le=10, description="Fit score from 1-10 against ICP")
    summary: str = Field(..., max_length=600, description="Company operations summary")
    pros: list[str] = Field(..., max_length=6, description="Key workflow bottlenecks suitable for automation")
    cons: list[str] = Field(..., max_length=6, description="Potential friction points or risks")
    suggested_angle: str = Field(..., max_length=400, description="Specific pitch hook")

    model_config = ConfigDict(extra="ignore")

    @field_validator("summary", mode="before")
    @classmethod
    def _sanitize_summary(cls, v: Any) -> str:
        text = str(v or "")
        return text[:590] if len(text) > 590 else text

    @field_validator("suggested_angle", mode="before")
    @classmethod
    def _sanitize_angle(cls, v: Any) -> str:
        text = str(v or "")
        return text[:390] if len(text) > 390 else text

    @field_validator("pros", "cons", mode="before")
    @classmethod
    def _sanitize_list(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(item)[:200] for item in v[:5]]
        if isinstance(v, str):
            return [v[:200]]
        return []


class EmailDraft(BaseModel):
    """Outreach email copy generated for an approved lead."""

    subject: str = Field(..., max_length=150, description="Short, lowercase, punchy subject")
    body: str = Field(..., max_length=1200, description="3-sentence value-driven cold pitch")

    model_config = ConfigDict(extra="ignore")

    @field_validator("subject", mode="before")
    @classmethod
    def _sanitize_subject(cls, v: Any) -> str:
        text = str(v or "")
        return text[:140] if len(text) > 140 else text

    @field_validator("body", mode="before")
    @classmethod
    def _sanitize_body(cls, v: Any) -> str:
        text = str(v or "")
        return text[:1150] if len(text) > 1150 else text


class LeadRecord(BaseModel):
    """Full database record schema corresponding to the 'leads' table."""

    id: UUID | str | None = Field(default=None, description="Primary key UUID")
    company_name: str = Field(..., description="Target company name")
    website_url: str = Field(..., description="Unique company website URL")
    decision_maker_name: str | None = Field(default=None, description="Executive name")
    decision_maker_title: str | None = Field(default=None, description="Executive title")
    decision_maker_email: str | None = Field(default=None, description="Contact email")
    fit_score: int | None = Field(default=None, ge=1, le=10, description="Fit score 1-10")
    summary: str | None = Field(default=None, description="Company operations summary")
    pros: list[str] | None = Field(default=None, description="Automation opportunities")
    cons: list[str] | None = Field(default=None, description="Risk factors")
    suggested_angle: str | None = Field(default=None, description="Cold pitch hook")
    email_subject: str | None = Field(default=None, description="Approved email subject")
    email_body: str | None = Field(default=None, description="Approved email body")
    status: LeadStatus = Field(default=LeadStatus.PENDING_LEAD_REVIEW, description="Current workflow status")
    telegram_message_id: int | None = Field(default=None, description="Telegram message ID for callback tracking")
    created_at: datetime | str | None = Field(default=None, description="Record creation timestamp")
    updated_at: datetime | str | None = Field(default=None, description="Record last update timestamp")

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    def to_db_dict(self) -> dict[str, Any]:
        """Convert record to a dict suitable for Supabase insertion/update."""
        return self.model_dump(exclude_none=True, mode="json")
