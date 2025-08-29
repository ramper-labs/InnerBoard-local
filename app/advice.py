"""
Orchestrates the Structured Reflection Extraction (SRE) and
Micro-Advice Composer (MAC) capabilities.
"""

import json
from app.llm import LocalLLM
from app.models import SREOutput, MACOutput
from pydantic import ValidationError

REQUIRED_SRE_KEYS = ["key_points", "blockers", "resources_needed", "confidence_delta"]
REQUIRED_MAC_KEYS = ["steps", "checklist", "urgency"]


def _normalize_sre_payload(data: dict) -> dict:
    """
    Repairs common issues in SRE JSON outputs:
    - Ensures all required keys exist
    - Coerces list fields to lists and limits to max 5 items
    - Clamps confidence_delta to [-1, 1]
    """
    repaired = dict(data) if isinstance(data, dict) else {}
    for key in ("key_points", "blockers", "resources_needed"):
        value = repaired.get(key)
        if not isinstance(value, list):
            repaired[key] = [] if value is None else [str(value)]
        else:
            # Convert to strings and limit to max 5 items
            repaired[key] = [str(x) for x in value][:5]
    # confidence_delta
    try:
        cd = float(repaired.get("confidence_delta", 0.0))
    except (TypeError, ValueError):
        cd = 0.0
    repaired["confidence_delta"] = max(-1.0, min(1.0, cd))
    return repaired


def _normalize_mac_payload(data: dict) -> dict:
    """
    Repairs common issues in MAC JSON outputs:
    - Ensures all required keys exist
    - Coerces list fields to lists
    - Validates urgency string
    """
    repaired = dict(data) if isinstance(data, dict) else {}
    for key in ("steps", "checklist"):
        value = repaired.get(key)
        if not isinstance(value, list):
            repaired[key] = [] if value is None else [str(value)]
        else:
            repaired[key] = [str(x) for x in value]
    urgency = str(repaired.get("urgency", "medium")).lower()
    if urgency not in ("low", "medium", "high"):
        urgency = "medium"
    repaired["urgency"] = urgency
    return repaired


def _fallback_mac_from_sre(sre: SREOutput) -> MACOutput:
    """Create a minimal, pragmatic MACOutput from SRE when model output is insufficient."""
    first_blocker = sre.blockers[0] if sre.blockers else "onboarding tasks"
    first_resource = (
        sre.resources_needed[0] if sre.resources_needed else "documentation"
    )
    steps = [
        f"Book a 20-min help session about {first_blocker}",
        f"Find and read {first_resource}",
        "Create a short checklist of next steps",
    ]
    # Ensure 3-6 items
    if len(steps) < 3:
        steps.append("Draft a question in the team channel")
    checklist = [
        "Session scheduled",
        "Doc link saved",
        "Question drafted",
        "Action items noted",
        "Progress reviewed",
    ]
    # Heuristic urgency
    urgent_set = {"env", "k8s", "access"}
    urgency = (
        "high" if any(cat in " ".join(sre.blockers) for cat in urgent_set) else "medium"
    )
    return MACOutput(steps=steps[:6], checklist=checklist[:5], urgency=urgency)


class AdviceService:
    """
    A service to process reflections and generate advice.
    """

    def __init__(self, llm: LocalLLM):
        """
        Initializes the service with a local LLM instance.

        Args:
            llm (LocalLLM): An initialized LocalLLM object.
        """
        self.llm = llm
        self._load_prompts()

    def _load_prompts(self):
        """Loads the system prompts from the prompts/ directory."""
        with open("prompts/sre_system_prompt.txt", "r") as f:
            self.sre_prompt = f.read()
        with open("prompts/mac_system_prompt.txt", "r") as f:
            self.mac_prompt = f.read()

    def get_structured_reflection(self, raw_text: str) -> SREOutput:
        """
        Uses the SRE model to extract structured data from a raw reflection.
        """
        messages = [
            {"role": "system", "content": self.sre_prompt},
            {"role": "user", "content": f"Reflection: {raw_text}"},
        ]

        raw_json = self.llm.generate(messages)

        try:
            cleaned_json = (
                raw_json.strip().replace("```json", "").replace("```", "").strip()
            )
            data = json.loads(cleaned_json)
            # Repair payload before validation
            repaired = _normalize_sre_payload(data)
            # Ensure required keys exist
            for k in REQUIRED_SRE_KEYS:
                if k not in repaired:
                    repaired[k] = [] if k != "confidence_delta" else 0.0
            return SREOutput(**repaired)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to decode LLM output as JSON: {e}\nRaw output: {raw_json}"
            )
        except ValidationError as e:
            raise ValueError(
                f"LLM output did not match SRE schema: {e}\nRaw output: {raw_json}"
            )

    def get_micro_advice(self, sre_output: SREOutput) -> MACOutput:
        """
        Uses the MAC model to generate actionable advice from structured data.
        """
        sre_json = sre_output.model_dump_json()

        messages = [
            {"role": "system", "content": self.mac_prompt},
            {"role": "user", "content": sre_json},
        ]

        raw_json = self.llm.generate(messages)

        try:
            cleaned_json = (
                raw_json.strip().replace("```json", "").replace("```", "").strip()
            )
            data = json.loads(cleaned_json)
            repaired = _normalize_mac_payload(data)
            for k in REQUIRED_MAC_KEYS:
                if k not in repaired:
                    repaired[k] = [] if k in ("steps", "checklist") else "medium"
            candidate = MACOutput(**repaired)
            # If steps too short, synthesize fallback
            if len(candidate.steps) < 3:
                return _fallback_mac_from_sre(sre_output)
            return candidate
        except json.JSONDecodeError as e:
            # Fallback on JSON parse error
            return _fallback_mac_from_sre(sre_output)
        except ValidationError:
            # Fallback on schema error
            return _fallback_mac_from_sre(sre_output)


def main():
    """
    Demonstrates the full advice generation pipeline.
    NOTE: This will be slow as it loads the full model.
    """
    print("--- Advice Service Demonstration ---")
    try:
        llm = LocalLLM()
        service = AdviceService(llm)
        reflection_text = (
            "I'm stuck on the new authentication service. The documentation seems to be for an "
            "older version of the code, and I can't get the JWT token to validate. I've been "
            "spinning my wheels for hours. My confidence is pretty low right now."
        )
        print(f"\nProcessing reflection:\n'{reflection_text}'")
        print("\nStep 1: Extracting structured reflection (SRE)...")
        sre_result = service.get_structured_reflection(reflection_text)
        print("SRE Output:")
        print(sre_result.model_dump_json(indent=2))
        print("\nStep 2: Composing micro-advice (MAC)...")
        mac_result = service.get_micro_advice(sre_result)
        print("MAC Output:")
        print(mac_result.model_dump_json(indent=2))
    except Exception as e:
        print(f"\nAn error occurred during the demonstration: {e}")


if __name__ == "__main__":
    main()
