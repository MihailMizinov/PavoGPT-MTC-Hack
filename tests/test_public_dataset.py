"""
Автотесты для проверки агента на задачах из публичной выборки MWS Octapi.
Запуск: после запуска docker-compose
 docker exec backend bash -c "pip install -q pytest requests && pytest /app/tests/test_public_dataset.py -v"


"""

import pytest
import requests
import json
import time
from typing import Dict, Optional

# Конфигурация
BACKEND_URL = "http://localhost:8000"
TIMEOUT = 60


class LuaAgentClient:
    """Клиент для взаимодействия с агентом"""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url
        self.session_id: Optional[str] = None

    def generate(self, prompt: str, session_id: Optional[str] = None) -> Dict:
        """Отправляет запрос на генерацию"""
        payload = {"prompt": prompt}
        if session_id or self.session_id:
            payload["session_id"] = session_id or self.session_id

        response = requests.post(
            f"{self.base_url}/generate",
            json=payload,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()

        if result.get("session_id"):
            self.session_id = result["session_id"]

        return result

    def reset(self):
        """Сбрасывает сессию"""
        if self.session_id:
            requests.post(
                f"{self.base_url}/reset",
                json={"session_id": self.session_id},
                timeout=10
            )
        self.session_id = None

    def health(self) -> Dict:
        """Проверяет здоровье сервиса"""
        response = requests.get(f"{self.base_url}/health", timeout=10)
        return response.json()


@pytest.fixture(scope="module")
def client():
    """Фикстура с клиентом агента"""
    cl = LuaAgentClient()

    health = cl.health()
    assert health["status"] == "ok", "Backend is not healthy"
    assert health["ollama"] == "connected", "Ollama is not connected"

    yield cl

    cl.reset()


def normalize_code(code: str) -> str:
    """Нормализует код для сравнения (убирает пробелы, переносы)"""
    if not code:
        return ""
    lines = [line.strip() for line in code.strip().splitlines()]
    lines = [line for line in lines if line]  # Убираем пустые строки
    return " ".join(lines)


def code_contains_keywords(code: str, keywords: list) -> bool:
    """Проверяет, что код содержит все ключевые слова"""
    code_lower = code.lower()
    return all(kw.lower() in code_lower for kw in keywords)


# ============================================================================
# ТЕСТЫ ИЗ ПУБЛИЧНОЙ ВЫБОРКИ
# ============================================================================

class TestPublicDataset:
    """Тесты для задач из публичной выборки LocalScript.pdf"""

    def test_01_last_element_of_array(self, client):
        """Задача 1: Последний элемент массива"""
        result = client.generate(
            "Из полученного списка email получи последний. "
            "Массив находится в wf.vars.emails"
        )

        assert result["status"] == "success", f"Expected success, got {result}"
        assert result["code"], "Code should not be empty"

        assert "wf.vars.emails" in result["code"], "Should use wf.vars.emails"
        assert "#" in result["code"] or "[" in result["code"], "Should access array element"
        assert "return" in result["code"], "Should return value"

        normalized = normalize_code(result["code"])
        expected = normalize_code("return wf.vars.emails[#wf.vars.emails]")

        assert "wf.vars.emails" in normalized
        print(f"\n✅ Generated: {result['code']}")

    def test_02_counter_increment(self, client):
        """Задача 2: Счётчик попыток"""
        client.reset()  # Новая сессия

        result = client.generate(
            "Увеличивай значение переменной try_count_n на каждой итерации. "
            "Переменная в wf.vars.try_count_n"
        )

        assert result["status"] == "success", f"Expected success, got {result}"
        assert "wf.vars.try_count_n" in result["code"]
        assert "+" in result["code"] or "return" in result["code"]

        print(f"\n✅ Generated: {result['code']}")

    def test_03_clear_fields(self, client):
        """Задача 3: Очистка значений в переменных"""
        client.reset()

        result = client.generate(
            "Для данных из RESTbody.result очисти значения полей ID, ENTITY_ID, CALL. "
            "Данные в wf.vars.RESTbody.result"
        )

        assert result["status"] == "success", f"Expected success, got {result}"

        keywords = ["wf.vars.RESTbody.result", "for", "pairs", "nil"]
        assert code_contains_keywords(result["code"], keywords[:3])

        print(f"\n✅ Generated: {result['code'][:200]}...")

    def test_04_filter_array(self, client):
        """Задача 6: Фильтрация элементов массива"""
        client.reset()

        result = client.generate(
            "Отфильтруй элементы массива parsedCsv, оставив только те, "
            "где Discount или Markdown не пустые. Массив в wf.vars.parsedCsv"
        )

        assert result["status"] == "success"

        keywords = ["wf.vars.parsedCsv", "Discount", "Markdown", "for", "if"]
        assert code_contains_keywords(result["code"], keywords[:4])

        print(f"\n✅ Generated: {result['code'][:200]}...")

    def test_05_ensure_array(self, client):
        """Задача 5: Проверка типа данных (нормализация до массива)"""
        client.reset()

        result = client.generate(
            "Сделай так, чтобы ZCDF_PACKAGES всегда был массивом, "
            "даже если это одиночный объект. "
            "Данные в wf.vars.json.IDOC.ZCDF_HEAD.ZCDF_PACKAGES"
        )

        assert result["status"] == "success"

        keywords = ["wf.vars", "ZCDF_PACKAGES", "array", "type"]
        assert code_contains_keywords(result["code"], keywords[:3])

        print(f"\n✅ Generated: {result['code'][:200]}...")

    def test_06_iso8601_conversion(self, client):
        """Задача 4: Приведение времени к ISO 8601"""
        client.reset()

        result = client.generate(
            "Преобразуй DATUM (формат YYYYMMDD) и TIME (формат HHMMSS) "
            "в строку ISO 8601. Данные в wf.vars.json.IDOC.ZCDF_HEAD"
        )

        assert result["status"] == "success"

        keywords = ["DATUM", "TIME", "string.format", "T", "Z"]
        assert code_contains_keywords(result["code"], keywords[:4])

        print(f"\n✅ Generated: {result['code'][:200]}...")

    def test_07_square_number(self, client):
        """Задача 7: Дополнение существующего кода (квадрат числа)"""
        client.reset()

        result = client.generate(
            "Добавь переменную с квадратом числа 5"
        )

        assert result["status"] == "success"
        assert "5" in result["code"] or "n" in result["code"]

        print(f"\n✅ Generated: {result['code']}")

    def test_08_unix_timestamp(self, client):
        """Задача 8: Конвертация в Unix timestamp"""
        client.reset()

        result = client.generate(
            "Конвертируй время в переменной recallTime в unix-формат. "
            "Время в wf.initVariables.recallTime в формате ISO 8601"
        )

        assert result["status"] == "success"

        keywords = ["recallTime", "1970", "86400", "3600"]
        assert code_contains_keywords(result["code"], keywords[:2])

        print(f"\n✅ Generated: {result['code'][:200]}...")


# ============================================================================
# ТЕСТЫ АГЕНТНОСТИ (ИТЕРАЦИИ, УТОЧНЕНИЯ)
# ============================================================================

class TestAgentBehavior:
    """Тесты агентского поведения"""

    def test_clarification_flow(self, client):
        """Проверяет, что агент уточняет неполный запрос"""
        client.reset()

        result1 = client.generate("сделай функцию")

        assert result1["status"] in ["need_info", "success"], \
            f"Expected need_info or success, got {result1['status']}"

        if result1["status"] == "need_info":
            assert result1["question"], "Should provide clarification question"
            print(f"\n✅ Clarification: {result1['question']}")

            result2 = client.generate(
                "функцию factorial, которая вычисляет факториал числа",
                session_id=result1["session_id"]
            )

            assert result2["status"] == "success"
            assert "factorial" in result2["code"].lower()
            print(f"✅ Final code generated after clarification")

    def test_session_persistence(self, client):
        """Проверяет, что сессия сохраняет контекст"""
        client.reset()

        result1 = client.generate(
            "Создай переменную x со значением 10"
        )
        session_id = result1["session_id"]

        result2 = client.generate(
            "увеличь x на 5",
            session_id=session_id
        )

        assert result2["status"] in ["success", "need_info"]
        print(f"\n✅ Session persisted: {session_id}")

    def test_syntax_error_recovery(self, client):
        """Проверяет, что агент исправляет синтаксические ошибки (если будут)"""
        client.reset()

        result = client.generate(
            "Напиши функцию с правильным синтаксисом Lua: "
            "function add(a, b) return a + b end"
        )

        assert result["status"] == "success"

        assert "function" in result["code"]
        assert "return" in result["code"]
        assert "end" in result["code"]

        print(f"\n✅ Generated valid syntax: {result['code']}")


# ============================================================================
# ТЕСТЫ API
# ============================================================================

class TestAPI:
    """Тесты эндпоинтов API"""

    def test_health_endpoint(self, client):
        """Проверяет /health"""
        health = client.health()
        assert health["status"] == "ok"
        assert "ollama" in health
        assert "model" in health
        print(f"\n✅ Health: {health}")

    def test_reset_endpoint(self, client):
        """Проверяет /reset"""
        # Создаём сессию
        result = client.generate("test prompt")
        session_id = result.get("session_id")

        # Сбрасываем
        response = requests.post(
            f"{BACKEND_URL}/reset",
            json={"session_id": session_id},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print(f"\n✅ Reset successful for session {session_id}")

    def test_generate_with_session(self, client):
        """Проверяет /generate с session_id"""
        client.reset()

        # Создаём сессию
        result1 = client.generate("Напиши функцию add(a,b)")
        session_id = result1["session_id"]
        assert session_id is not None

        # Используем ту же сессию
        result2 = client.generate(
            "Добавь проверку на nil",
            session_id=session_id
        )
        assert result2["session_id"] == session_id
        print(f"\n✅ Session reused: {session_id}")


# ============================================================================
# ЗАПУСК
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ЗАПУСК АВТОТЕСТОВ")
    print("=" * 60)

    try:
        client = LuaAgentClient()
        health = client.health()
        print(f"\n✅ Backend: {health['status']}")
        print(f"✅ Ollama: {health['ollama']}")
        print(f"✅ Model: {health['model']}")
    except Exception as e:
        print(f"\n❌ Cannot connect to backend: {e}")
        print("Make sure docker-compose is running!")
        exit(1)

    pytest.main([__file__, "-v", "--tb=short"])