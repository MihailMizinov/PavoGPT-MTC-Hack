import os
import logging
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ML_PATH = Path(__file__).parent.parent.parent / "ml" / "src"
if str(ML_PATH) not in sys.path:
    sys.path.insert(0, str(ML_PATH))

from app.api.routes import router
from app.services.session_service import init_session_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5-coder:1.5b-instruct-q4_K_M")

init_session_service(OLLAMA_URL, MODEL_NAME)

app = FastAPI(
    title="Lua Agent System API",
    description="""
    ## Локальный AI-агент для генерации Lua-кода

    ### Технические детали:
    - Ollama URL: `{ollama_url}`
    - Модель: `{model_name}`
    """.format(ollama_url=OLLAMA_URL, model_name=MODEL_NAME),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения"""
    logging.info(f"Starting Lua Agent System with Ollama at {OLLAMA_URL}")
    logging.info(f"Using model: {MODEL_NAME}")
    logging.info("Swagger UI available at: http://localhost:8000/docs")
    logging.info("ReDoc available at: http://localhost:8000/redoc")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка ресурсов при завершении работы"""
    logging.info("Shutting down Lua Agent System")


@app.get("/health", tags=["health"])
async def health_check():
    """
    Проверка работоспособности сервиса

    Возвращает статус сервиса и информацию о текущей конфигурации.

    **Response:**
    - `status`: "ok" если сервис работает
    - `ollama_url`: URL подключения к Ollama
    - `model`: Используемая модель
    """
    return {
        "status": "ok",
        "ollama_url": OLLAMA_URL,
        "model": MODEL_NAME,
        "service": "Lua Agent System"
    }
