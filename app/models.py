"""
Pydantic models for structured data used throughout the application.
"""

from pydantic import BaseModel, Field
from typing import List


class Reflection(BaseModel):
    """Model for a user's journal entry."""

    raw_text: str


class SREKeySuccess(BaseModel):
    """Represents a concrete success derived from console activity."""

    desc: str = Field(..., description="Short description of what worked or was achieved")
    specifics: str = Field(
        ..., description="Commands, artifacts, or concrete details supporting the success"
    )
    adjacent_context: str = Field(
        ..., description="Related context like services, repos, or files involved"
    )


class SREBlocker(BaseModel):
    """Represents a blocker derived from console activity."""

    desc: str = Field(..., description="What is blocked or failing")
    impact: str = Field(..., description="Impact of the blocker on outcomes or timelines")
    owner_hint: str = Field(..., description="Likely owner/team/role to help")
    resolution_hint: str = Field(..., description="Concrete next step to move forward")


class SRESession(BaseModel):
    """A single session summary extracted from console activity."""

    summary: str = Field(..., description="High-level summary for the session")
    key_successes: List[SREKeySuccess] = Field(
        default_factory=list, description="1–5 key successes from the session"
    )
    blockers: List[SREBlocker] = Field(
        default_factory=list, description="0–5 blockers from the session"
    )
    resources: List[str] = Field(
        default_factory=list, description="0–7 resource strings (links, commands, paths)"
    )


class MACMeetingPrep(BaseModel):
    """Meeting-prep outputs: team/manager updates and actionable recommendations."""

    team_update: List[str] = Field(
        default_factory=list, description="2–5 peer-friendly progress updates"
    )
    manager_update: List[str] = Field(
        default_factory=list, description="2–5 outcome/risks/timeline updates"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="2–5 concrete next-step recommendations"
    )


def main():
    """Quick demo of the Pydantic models."""
    example = SRESession(
        summary="Investigated ingress routing and validated service wiring",
        key_successes=[
            SREKeySuccess(
                desc="Validated cluster DNS",
                specifics="ran kubectl exec busybox -- nslookup service",
                adjacent_context="k8s cluster dev-east, svc payment-api",
            )
        ],
        blockers=[
            SREBlocker(
                desc="Ingress rule not matching host",
                impact="Service unreachable from external LB",
                owner_hint="Platform team",
                resolution_hint="Compare nginx ingress annotations with prod",
            )
        ],
        resources=["docs/ingress.md"],
    )
    print(example.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
