"""
Transforms console activity into structured sessions and meeting-prep outputs.
"""

import json
from typing import List
from pydantic import ValidationError
from app.llm import LocalLLM
from app.models import (
    SRESession,
    MACMeetingPrep,
)


class AdviceService:
    """Service to process console activity and generate meeting-prep outputs."""

    def __init__(self, llm: LocalLLM):
        self.llm = llm
        self._load_prompts()

    def _load_prompts(self):
        with open("prompts/sre_system_prompt.txt", "r") as f:
            self.sre_prompt = f.read()
        with open("prompts/mac_system_prompt.txt", "r") as f:
            self.mac_prompt = f.read()

    def get_console_insights(self, console_text: str) -> List[SRESession]:
        """Extract per-session insights from raw console activity text."""
        messages = [
            {"role": "system", "content": self.sre_prompt},
            {"role": "user", "content": console_text},
        ]
        raw_json = self.llm.generate(messages)
        try:
            cleaned_json = (
                raw_json.strip().replace("```json", "").replace("```", "").strip()
            )
            data = json.loads(cleaned_json)
            if not isinstance(data, list):
                data = []
            sessions: List[SRESession] = []
            for item in data:
                try:
                    sessions.append(SRESession(**item))
                except ValidationError:
                    # Skip invalid items rather than failing the whole batch
                    continue
            return sessions
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to decode SRE output as JSON: {e}\nRaw output: {raw_json}"
            )

    def get_meeting_prep(self, sessions: List[SRESession]) -> MACMeetingPrep:
        """Generate team/manager updates and recommendations from SRE sessions."""
        sessions_json = json.dumps([s.model_dump() for s in sessions])
        messages = [
            {"role": "system", "content": self.mac_prompt},
            {"role": "user", "content": sessions_json},
        ]
        raw_json = self.llm.generate(messages)
        try:
            cleaned_json = (
                raw_json.strip().replace("```json", "").replace("```", "").strip()
            )
            data = json.loads(cleaned_json)
            # Ensure arrays exist
            for key in ("team_update", "manager_update", "recommendations"):
                if key not in data or not isinstance(data[key], list):
                    data[key] = []
            return MACMeetingPrep(**data)
        except json.JSONDecodeError as e:
            # If MAC decoding fails, return empty prep to avoid breaking CLI
            return MACMeetingPrep()


def main():
    print("--- Advice Service Demonstration (console -> meeting prep) ---")
    try:
        llm = LocalLLM()
        service = AdviceService(llm)
        console_text = (
            "kubectl get pods -n payments; kubectl describe ingress payments; git log -1;"
        )
        sessions = service.get_console_insights(console_text)
        print("SRE Sessions:")
        print(json.dumps([s.model_dump() for s in sessions], indent=2))
        prep = service.get_meeting_prep(sessions)
        print("\nMeeting Prep:")
        print(prep.model_dump_json(indent=2))
    except Exception as e:
        print(f"\nAn error occurred during the demonstration: {e}")


if __name__ == "__main__":
    main()
