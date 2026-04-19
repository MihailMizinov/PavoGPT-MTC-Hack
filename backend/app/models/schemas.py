from pydantic import BaseModel, Field
from typing import Optional, Literal


class GenerateRequest(BaseModel):
    """Запрос на генерацию Lua-кода"""
    prompt: str = Field(
        ...,
        description="Текстовое описание желаемого Lua-скрипта или вопрос по существующему коду",
        example="Создать функцию для вычисления факториала числа",
        min_length=1,
        max_length=10000
    )
    session_id: Optional[str] = Field(
        None,
        description="ID существующей сессии. Если не указан, создается новая сессия",
        example="session_abc123"
    )

    class Config:
        schema_extra = {
            "example": {
                "prompt": "Напиши функцию для сортировки массива пузырьком",
                "session_id": "session_xyz789"
            }
        }


class GenerateResponse(BaseModel):
    """Ответ на запрос генерации Lua-кода"""
    status: Literal["success", "need_info", "error"] = Field(
        ...,
        description="Статус обработки запроса:\n"
                    "- `success`: код успешно сгенерирован\n"
                    "- `need_info`: требуется дополнительная информация\n"
                    "- `error`: произошла ошибка при генерации"
    )
    code: Optional[str] = Field(
        None,
        description="Сгенерированный Lua-код (при status='success' или status='error')"
    )
    question: Optional[str] = Field(
        None,
        description="Уточняющий вопрос (при status='need_info')"
    )
    message: Optional[str] = Field(
        None,
        description="Сообщение об ошибке (при status='error')"
    )
    session_id: Optional[str] = Field(
        None,
        description="ID сессии для дальнейших запросов"
    )

    class Config:
        schema_extra = {
            "examples": {
                "success": {
                    "value": {
                        "status": "success",
                        "code": "function factorial(n)\n    if n <= 1 then\n        return 1\n    end\n    return n * factorial(n-1)\nend",
                        "session_id": "session_abc123"
                    }
                },
                "need_info": {
                    "value": {
                        "status": "need_info",
                        "question": "Какой тип данных должен обрабатывать скрипт?",
                        "session_id": "session_abc123"
                    }
                },
                "error": {
                    "value": {
                        "status": "error",
                        "message": "Не удалось сгенерировать корректный Lua-код",
                        "code": "-- Generated code with errors\nfunction test(\n    print('missing closing paren')\nend",
                        "session_id": "session_abc123"
                    }
                }
            }
        }


class ResetRequest(BaseModel):
    """Запрос на сброс сессии"""
    session_id: str = Field(
        ...,
        description="ID сессии для сброса",
        example="session_abc123",
        min_length=1
    )

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123"
            }
        }


class ResetResponse(BaseModel):
    """Ответ на сброс сессии"""
    status: str = Field(
        ...,
        description="Статус операции",
        example="ok"
    )
    message: str = Field(
        ...,
        description="Сообщение о результате операции",
        example="Session reset successfully"
    )

    class Config:
        schema_extra = {
            "example": {
                "status": "ok",
                "message": "Session reset"
            }
        }


class HealthResponse(BaseModel):
    """Информация о состоянии сервиса"""
    status: str = Field(
        ...,
        description="Общий статус сервиса",
        example="ok"
    )
    ollama: str = Field(
        ...,
        description="Статус подключения к Ollama (connected/disconnected)",
        example="connected"
    )
    model: str = Field(
        ...,
        description="Используемая модель Ollama",
        example="qwen2.5-coder:1.5b-instruct-q4_K_M"
    )

    class Config:
        schema_extra = {
            "example": {
                "status": "ok",
                "ollama": "connected",
                "model": "qwen2.5-coder:1.5b-instruct-q4_K_M"
            }
        }