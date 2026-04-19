import sys
from pathlib import Path

ML_PATH = Path(__file__).parent.parent.parent.parent / "ml" / "src"
if str(ML_PATH) not in sys.path:
    sys.path.insert(0, str(ML_PATH))

import uuid
from typing import Dict, Optional
from agent.orchestrator import AgentOrchestrator
from agent.llm_client import OllamaClient


class SessionService:
    def __init__(self, ollama_url: str, model_name: str):
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.sessions: Dict[str, AgentOrchestrator] = {}

    def _create_orchestrator(self) -> AgentOrchestrator:
        llm_client = OllamaClient(
            base_url=self.ollama_url,
            model=self.model_name,
            num_ctx=4096,
            num_predict=256
        )
        return AgentOrchestrator(llm_client=llm_client, max_iterations=3)

    def get_or_create(self, session_id: Optional[str]) -> tuple[str, AgentOrchestrator]:
        if session_id and session_id in self.sessions:
            return session_id, self.sessions[session_id]

        new_session_id = session_id or str(uuid.uuid4())
        orchestrator = self._create_orchestrator()
        self.sessions[new_session_id] = orchestrator
        return new_session_id, orchestrator

    def reset(self, session_id: str) -> bool:
        if session_id in self.sessions:
            self.sessions[session_id].reset()
            return True
        return False


_session_service: Optional[SessionService] = None


def init_session_service(ollama_url: str, model_name: str):
    global _session_service
    _session_service = SessionService(ollama_url, model_name)


def get_session_service() -> SessionService:
    if _session_service is None:
        raise RuntimeError("SessionService not initialized")
    return _session_service
