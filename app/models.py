"""
Pydantic models for structured data used throughout the application.
"""
from pydantic import BaseModel, Field
from typing import List, Literal

class Reflection(BaseModel):
    """Model for a user's journal entry."""
    raw_text: str

class SREOutput(BaseModel):
    """
    Structured Reflection Extraction (SRE) model.
    Represents the structured data extracted from a raw reflection.
    """
    key_points: List[str] = Field(
        ...,
        description="A list of terse, key points from the reflection.",
        max_items=5
    )
    blockers: List[str] = Field(
        ...,
        description="A list of identified blockers or challenges.",
        max_items=5
    )
    resources_needed: List[str] = Field(
        ...,
        description="A list of resources or help needed to overcome blockers.",
        max_items=5
    )
    confidence_delta: float = Field(
        ...,
        description="A float between -1.0 and 1.0 indicating the change in confidence.",
        ge=-1.0,
        le=1.0
    )

class MACOutput(BaseModel):
    """
    Micro-Advice Composer (MAC) model.
    Represents the actionable advice generated from a structured reflection.
    """
    steps: List[str] = Field(
        ...,
        description="A list of 3-6 imperative, time-bound steps to take.",
        min_items=3,
        max_items=6
    )
    checklist: List[str] = Field(
        ...,
        description="A list of up to 5 checklist items for progress tracking.",
        max_items=5
    )
    urgency: Literal['low', 'medium', 'high'] = Field(
        ...,
        description="The assessed urgency of the situation."
    )

def main():
    """Demonstrates the usage of the Pydantic models."""
    print("Demonstrating SREOutput model...")
    sre_data = {
        "key_points": ["Ingress not routing", "Docs unclear"],
        "blockers": ["k8s ingress config", "missing example"],
        "resources_needed": ["working ingress example", "cluster access"],
        "confidence_delta": -0.4
    }
    try:
        sre_model = SREOutput(**sre_data)
        print("SREOutput validation successful:")
        print(sre_model.model_dump_json(indent=2))
    except Exception as e:
        print(f"SREOutput validation failed: {e}")

    print("\nDemonstrating MACOutput model...")
    mac_data = {
        "steps": [
            "Book a 15-min pair session with a senior engineer.",
            "Find a working ingress YAML in the team's repo.",
            "Document the fix in a personal snippets file."
        ],
        "checklist": [
            "Session booked",
            "YAML found",
            "Snippet saved"
        ],
        "urgency": "high"
    }
    try:
        mac_model = MACOutput(**mac_data)
        print("MACOutput validation successful:")
        print(mac_model.model_dump_json(indent=2))
    except Exception as e:
        print(f"MACOutput validation failed: {e}")

if __name__ == "__main__":
    main()
