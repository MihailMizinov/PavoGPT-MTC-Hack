import requests
from typing import List, Dict

class OllamaClient:
    def __init__(self, base_url: str, model: str, num_ctx: int = 4096, num_predict: int = 256):
        self.base_url = base_url
        self.model = model
        self.num_ctx = num_ctx
        self.num_predict = num_predict

    def _format_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Преобразует список сообщений в единый промпт для /api/generate"""
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        parts.append("Assistant:")
        return "\n".join(parts)

    def generate(self, messages: List[Dict[str, str]]) -> str:
        prompt = self._format_messages_to_prompt(messages)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
                "temperature": 0.2,
                "top_p": 0.9,
                "batch_size": 1,
                "parallel": 1
            }
        }
        response = requests.post(f"{self.base_url}/api/generate", json=payload)
        response.raise_for_status()
        return response.json()["response"]

    def cancel(self) -> bool:
        """
        Останавливает текущую генерацию модели (через /api/stop).
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/stop",
                json={"model": self.model},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False