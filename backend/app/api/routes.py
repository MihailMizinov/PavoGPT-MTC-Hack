import logging
from fastapi import APIRouter, HTTPException, status
from app.models.schemas import (
    GenerateRequest, GenerateResponse,
    ResetRequest, ResetResponse, HealthResponse
)
from app.services.session_service import get_session_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Lua Agent API"])


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Генерация Lua-кода",
    description="""
    Генерирует Lua-код на основе текстового описания и может доработать код по просьбе.

    **Возможные статусы ответа:**
    - `success`: Код успешно сгенерирован и прошел валидацию
    - `need_info`: Требуется уточнение для генерации корректного кода
    - `error`: Произошла ошибка при генерации или валидации
    """
)
async def generate(request: GenerateRequest):
    try:
        service = get_session_service()
        session_id, orchestrator = service.get_or_create(request.session_id)

        logger.info(f"Processing generation request for session {session_id}")
        logger.debug(f"Prompt: {request.prompt[:100]}...")

        result = orchestrator.run_iteration(request.prompt)

        response = GenerateResponse(
            status=result["status"],
            session_id=session_id
        )

        if result["status"] == "success":
            response.code = result["code"]
            logger.info(f"Successfully generated code for session {session_id}")
        elif result["status"] == "need_info":
            response.question = result["question"]
            logger.info(f"Need additional info for session {session_id}")
        elif result["status"] == "error":
            response.message = result["message"]
            if result.get("code"):
                response.code = result["code"]
            logger.error(f"Error generating code for session {session_id}: {result['message']}")

        return response

    except Exception as e:
        logger.exception(f"Unexpected error in /generate: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/reset",
    response_model=ResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Сброс сессии",
    description="""
    Сбрасывает контекст указанной сессии, очищая историю взаимодействий.

    **Использование:**
    - Для начала работы с чистым контекстом
    - При смене задачи или проекта
    - Для освобождения ресурсов

    """
)
async def reset_session(request: ResetRequest):
    """
    Сбрасывает контекст сессии по ID.

    - **session_id**: ID сессии для сброса
    """
    service = get_session_service()
    success = service.reset(request.session_id)

    if success:
        logger.info(f"Session {request.session_id} reset successfully")
        return ResetResponse(
            status="ok",
            message=f"Session {request.session_id} reset successfully"
        )
    else:
        logger.warning(f"Attempt to reset non-existent session: {request.session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {request.session_id} not found"
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Проверка состояния сервиса",
    description="""
    Проверяет работоспособность сервиса и подключения к Ollama.

    **Используется для:**
    - Мониторинга состояния системы
    - Проверки доступности перед началом работы
    - Диагностики проблем подключения

    **Возможные значения `ollama`:**
    - `connected`: Ollama доступен и отвечает на запросы
    - `disconnected`: Ollama недоступен или не отвечает
    """
)
async def health():
    """
    Возвращает текущее состояние сервиса и подключения к Ollama.
    """
    import requests
    import os

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model_name = os.getenv("MODEL_NAME", "unknown")
    ollama_status = "disconnected"

    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            ollama_status = "connected"
            logger.debug(f"Ollama connection successful at {ollama_url}")
        else:
            logger.warning(f"Ollama returned status {response.status_code}")
    except requests.exceptions.Timeout:
        logger.warning(f"Ollama connection timeout at {ollama_url}")
    except requests.exceptions.ConnectionError:
        logger.warning(f"Cannot connect to Ollama at {ollama_url}")
    except Exception as e:
        logger.error(f"Unexpected error checking Ollama: {e}")

    return HealthResponse(
        status="ok",
        ollama=ollama_status,
        model=model_name
    )


@router.post("/cancel")
async def cancel_generation(session_id: str):
    """Отмена текущей генерации"""
    service = get_session_service()
    _, orchestrator = service.get_or_create(session_id)

    success = orchestrator.cancel_generation()

    return {"status": "cancelled" if success else "failed"}