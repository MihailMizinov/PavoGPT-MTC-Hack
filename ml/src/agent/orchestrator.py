import re
import logging
from typing import Dict
from .llm_client import OllamaClient
from .validator import LuaValidator
from .prompt_builder import PromptBuilder
from .session import SessionManager

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self, llm_client: OllamaClient, max_iterations: int = 3):
        self.llm = llm_client
        self.validator = LuaValidator()
        self.prompt_builder = PromptBuilder()
        self.max_iterations = max_iterations
        self.session = SessionManager()

    def reset(self):
        self.session.clear()

    def _extract_code(self, text: str) -> str:
        # Ищем блок ```lua ... ``` или просто ``` ... ```
        match = re.search(r"```(?:lua)?\s*\n(.*?)\n\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            code = match.group(1).strip()
        else:
            # Пытаемся найти что-то похожее на код: начинается с local/function/return/print/for/if
            lines = text.split('\n')
            code_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and (stripped.startswith(('local', 'function', 'return', 'print', 'for', 'if', 'while', 'do', 'end')) or 
                                 stripped.startswith('--') or 
                                 re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*=', stripped)):
                    code_lines.append(line)
            code = '\n'.join(code_lines)
        # Очистка от мусора
        code = re.sub(r'[^\x20-\x7E\n\r\t]', '', code)
        code = code.replace('!function', 'function').replace('!', '')
        return code.strip()

    def _check_forbidden(self, code: str) -> tuple[bool, str]:
        forbidden = [
            ("os.date", "os.date is forbidden in MWS"),
            ("os.time", "os.time is forbidden in MWS"),
            ("os.execute", "os.execute is forbidden"),
            ("io.popen", "io.popen is forbidden"),
            ("debug.", "debug.* is forbidden"),
        ]
        for pattern, msg in forbidden:
            if pattern in code:
                return False, msg
        return True, ""

    def generate_code(self, user_input: str) -> str:
        self.session.add_message("user", user_input)
        system_prompt = self.prompt_builder.build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.session.get_history()
        response = self.llm.generate(messages)
        return self._extract_code(response)

    def run_iteration(self, user_request: str) -> Dict:
        complete, question = self._is_complete(user_request)
        if not complete:
            logger.info(f"Request incomplete: {user_request[:50]}...")
            return {"status": "need_info", "question": question, "code": None}

        code = self.generate_code(user_request)

        forbidden_ok, forbidden_msg = self._check_forbidden(code)
        if not forbidden_ok:
            logger.warning(f"Forbidden function detected: {forbidden_msg}")
            for i in range(self.max_iterations):
                fix_prompt = f"Убери запрещённую функцию. {forbidden_msg}\nИсправь код:\n```lua\n{code}\n```"
                self.session.add_message("user", fix_prompt)
                messages = [{"role": "system", "content": self.prompt_builder.build_system_prompt()}] + self.session.get_history()
                new_response = self.llm.generate(messages)
                code = self._extract_code(new_response)
                forbidden_ok, forbidden_msg = self._check_forbidden(code)
                if forbidden_ok:
                    break
            if not forbidden_ok:
                return {"status": "error", "message": f"Forbidden function after {self.max_iterations} fixes: {forbidden_msg}", "code": code}

        syntax_ok, syntax_msg = self.validator.check_syntax(code)
        if not syntax_ok:
            logger.info(f"Syntax error detected, attempting fixes...")
            for i in range(self.max_iterations):
                fix_prompt = f"Ошибка синтаксиса: {syntax_msg}\nИсправь код:\n```lua\n{code}\n```"
                self.session.add_message("user", fix_prompt)
                messages = [{"role": "system", "content": self.prompt_builder.build_system_prompt()}] + self.session.get_history()
                new_response = self.llm.generate(messages)
                code = self._extract_code(new_response)
                syntax_ok, syntax_msg = self.validator.check_syntax(code)
                if syntax_ok:
                    logger.info(f"Syntax fixed on attempt {i+1}")
                    break
            if not syntax_ok:
                logger.error(f"Syntax error persists after {self.max_iterations} fixes")
                return {"status": "error", "message": f"Syntax error after {self.max_iterations} fixes: {syntax_msg}", "code": code}

        lint_ok, lint_msg = self.validator.run_luacheck(code)
        if not lint_ok:
            logger.debug(f"Lint warnings: {lint_msg}")

        self.session.add_message("assistant", code)
        logger.info(f"Successfully generated code ({len(code)} chars)")
        return {"status": "success", "code": code, "syntax_ok": syntax_ok, "lint_warnings": lint_msg if not lint_ok else None}

    def _is_complete(self, user_request: str) -> tuple[bool, str]:
        # Твоя существующая логика (я её не трогаю)
        request_lower = user_request.lower().strip()
        vague_phrases = ["сделай", "напиши", "помоги", "хочу", "нужно"]
        if any(phrase in request_lower for phrase in vague_phrases) and len(request_lower) < 20:
            return False, "Уточните, пожалуйста: что именно должен делать скрипт?"
        complete_keywords = [
            "wf.vars", "wf.initvariables",
            "restbody", "result", "parsedcsv", "emails", "try_count",
            "recalltime", "idoc", "zcdf", "discount", "markdown",
            "очисти", "clear", "фильтр", "filter", "получи", "get",
            "увелич", "increment", "конвертируй", "convert",
            "последний", "last", "функци", "function", "return",
            "массив", "array", "время", "time", "unix", "iso"
        ]
        matches = sum(1 for kw in complete_keywords if kw in request_lower)
        if matches >= 2:
            return True, ""
        if len(request_lower) < 10:
            return False, "Пожалуйста, опишите задачу подробнее."
        return True, ""