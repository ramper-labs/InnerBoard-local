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
from app.utils import safe_json_loads
from app.config import config


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

    def _extract_json_array_text(self, raw_json: str) -> str:
        """Remove fences and isolate the outermost JSON array if present."""
        s = raw_json.strip().replace("```json", "").replace("```", "").strip()
        start = s.find("[")
        end = s.rfind("]")
        if start != -1 and end != -1 and end > start:
            return s[start : end + 1]
        return s

    def get_console_insights(self, console_text: str) -> List[SRESession]:
        """Extract per-session insights from raw console activity text."""
        messages = [
            {"role": "system", "content": self.sre_prompt},
            {"role": "user", "content": console_text},
        ]
        raw_json = self.llm.generate(messages)
        cleaned_json = self._extract_json_array_text(raw_json)
        data = safe_json_loads(cleaned_json, default=None)

        parse_failed = False

        # If single object returned, coerce into a list
        if data is None:
            obj = safe_json_loads(cleaned_json.strip().strip(","), default=None)
            if isinstance(obj, dict):
                data = [obj]
            else:
                parse_failed = True

        if not isinstance(data, list):
            data = []

        sessions: List[SRESession] = []
        for item in data:
            try:
                sessions.append(SRESession(**item))
            except ValidationError:
                continue

        if parse_failed:
            retry_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "The previous response was not valid JSON. "
                        "Respond with ONLY a JSON array of session objects matching the schema. "
                        "Do not include markdown or commentary."
                    ),
                }
            ]
            retry_temp = max(config.temperature - 0.2, 0.1)
            retry_raw = self.llm.generate(retry_messages, temperature=retry_temp)
            retry_clean = self._extract_json_array_text(retry_raw)
            retry_data = safe_json_loads(retry_clean, default=None)
            if isinstance(retry_data, dict):
                retry_data = [retry_data]
            if isinstance(retry_data, list):
                sessions = []
                for item in retry_data:
                    try:
                        sessions.append(SRESession(**item))
                    except ValidationError:
                        continue
        return sessions

    def get_meeting_prep(self, sessions: List[SRESession]) -> MACMeetingPrep:
        """Generate team/manager updates and recommendations from SRE sessions."""
        sessions_json = json.dumps([s.model_dump() for s in sessions])
        messages = [
            {"role": "system", "content": self.mac_prompt},
            {"role": "user", "content": sessions_json},
        ]
        raw_json = self.llm.generate(messages)
        cleaned_json = self._extract_json_array_text(raw_json)
        data = safe_json_loads(cleaned_json, default=None)
        if not isinstance(data, dict):
            retry_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "The previous response was not a valid JSON object. "
                        "Respond with ONLY a JSON object containing keys: "
                        "team_update, manager_update, recommendations (each an array). "
                        "Do not include markdown or commentary."
                    ),
                }
            ]
            retry_temp = max(config.temperature - 0.2, 0.1)
            retry_raw = self.llm.generate(retry_messages, temperature=retry_temp)
            cleaned_json = self._extract_json_array_text(retry_raw)
            data = safe_json_loads(cleaned_json, default=None)
            if not isinstance(data, dict):
                return MACMeetingPrep()

        for key in ("team_update", "manager_update", "recommendations"):
            if key not in data or not isinstance(data[key], list):
                data[key] = []
        return MACMeetingPrep(**data)


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
