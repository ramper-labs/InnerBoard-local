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
from app.logging_config import get_logger

logger = get_logger(__name__)


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
        s = raw_json.strip()
        
        # Remove markdown code fences
        s = s.replace("```json", "").replace("```", "").strip()
        
        # Look for JSON array
        start = s.find("[")
        end = s.rfind("]")
        if start != -1 and end != -1 and end > start:
            return s[start : end + 1]
        
        # Look for JSON object (fallback)
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return s[start : end + 1]
            
        return s

    def _extract_json_object_text(self, raw_json: str) -> str:
        """Remove fences and isolate the outermost JSON object if present."""
        s = raw_json.strip()
        
        # Remove markdown code fences
        s = s.replace("```json", "").replace("```", "").strip()
        
        # Look for JSON object first
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return s[start : end + 1]
        
        # Fallback to array
        start = s.find("[")
        end = s.rfind("]")
        if start != -1 and end != -1 and end > start:
            return s[start : end + 1]
            
        return s

    def get_console_insights(self, console_text: str) -> List[SRESession]:
        """Extract per-session insights from raw console activity text."""
        messages = [
            {"role": "system", "content": self.sre_prompt},
            {"role": "user", "content": f"Console activity to analyze:\n\n{console_text}\n\nReturn ONLY the JSON array, no explanations or markdown:"},
        ]
        raw_json = self.llm.generate(messages, max_new_tokens=config.max_tokens)
        logger.debug(f"Initial LLM response: {raw_json}")
        cleaned_json = self._extract_json_array_text(raw_json)
        logger.debug(f"Cleaned JSON: {cleaned_json}")
        data = safe_json_loads(cleaned_json, default=None)

        parse_failed = False

        # If single object returned, coerce into a list
        if data is None:
            logger.warning(f"Failed to parse initial response: {cleaned_json}")
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

        if parse_failed or not sessions:
            # More aggressive retry with explicit JSON-only instruction
            retry_messages = [
                {"role": "system", "content": "You must respond with ONLY valid JSON. No text, no markdown, no explanations. Just pure JSON."},
                {"role": "user", "content": f"Convert this console activity to a JSON array following this exact schema:\n[{{'summary': 'string', 'key_successes': [{{'desc': 'string', 'specifics': 'string', 'adjacent_context': 'string'}}], 'blockers': [{{'desc': 'string', 'impact': 'string', 'owner_hint': 'string', 'resolution_hint': 'string'}}], 'resources': ['string']}}]\n\nConsole activity:\n{console_text}\n\nJSON:"}
            ]
            retry_temp = max(config.temperature - 0.3, 0.0)
            retry_raw = self.llm.generate(retry_messages, temperature=retry_temp, max_new_tokens=config.max_tokens)
            logger.debug(f"Retry LLM response: {retry_raw}")
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
        sessions_json = json.dumps([s.model_dump() for s in sessions], indent=2)
        messages = [
            {"role": "system", "content": self.mac_prompt},
            {"role": "user", "content": f"SRE session data to analyze:\n\n{sessions_json}\n\nReturn ONLY the JSON object, no explanations or markdown:"},
        ]
        raw_json = self.llm.generate(messages, max_new_tokens=config.max_tokens)
        logger.debug(f"Initial MAC LLM response: {raw_json}")
        cleaned_json = self._extract_json_object_text(raw_json)
        logger.debug(f"Cleaned MAC JSON: {cleaned_json}")
        data = safe_json_loads(cleaned_json, default=None)
        
        if not isinstance(data, dict):
            # More aggressive retry with explicit JSON-only instruction
            retry_messages = [
                {"role": "system", "content": "You must respond with ONLY valid JSON. No text, no markdown, no explanations. Just pure JSON."},
                {"role": "user", "content": f"Convert these SRE sessions to a JSON object following this exact schema:\n{{'team_update': ['string'], 'manager_update': ['string'], 'recommendations': ['string']}}\n\nSRE sessions:\n{sessions_json}\n\nJSON:"}
            ]
            retry_temp = max(config.temperature - 0.3, 0.0)
            retry_raw = self.llm.generate(retry_messages, temperature=retry_temp, max_new_tokens=config.max_tokens)
            logger.debug(f"Retry MAC LLM response: {retry_raw}")
            cleaned_json = self._extract_json_object_text(retry_raw)
            data = safe_json_loads(cleaned_json, default=None)
            if not isinstance(data, dict):
                logger.warning("Failed to get valid MAC JSON response, returning empty")
                return MACMeetingPrep()

        # Ensure all required keys exist and are lists
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
