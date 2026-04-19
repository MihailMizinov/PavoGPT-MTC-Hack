from typing import List, Dict

class SessionManager:
    def __init__(self, max_history: int = 10):
        self.history: List[Dict[str, str]] = []
        self.max_history = max_history

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def get_history(self) -> List[Dict[str, str]]:
        return self.history

    def clear(self):
        self.history = []