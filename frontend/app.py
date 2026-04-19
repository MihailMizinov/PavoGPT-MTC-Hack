import asyncio
import chainlit as cl
import aiohttp
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

current_task = None


@cl.on_chat_start
async def on_chat_start():
    """Инициализация сессии при старте чата"""
    cl.user_session.set("chat_history", [])
    cl.user_session.set("session_id", None)
    cl.user_session.set("current_task", None)


@cl.on_message
async def main(message: cl.Message):
    """Обработка сообщения пользователя"""
    global current_task

    session_id = cl.user_session.get("session_id")
    chat_history = cl.user_session.get("chat_history")

    chat_history.append({"role": "user", "content": message.content})

    msg = cl.Message(content="")
    await msg.send()

    task = asyncio.create_task(
        process_generation(message.content, session_id, chat_history, msg)
    )

    cl.user_session.set("current_task", task)
    current_task = task

    try:
        await task
    except asyncio.CancelledError:
        await msg.update()
        await cl.Message(content="⏹️ **Генерация отменена.**").send()
    finally:
        cl.user_session.set("current_task", None)
        current_task = None


async def process_generation(prompt: str, session_id: str, chat_history: list, msg: cl.Message):
    """Основная логика генерации с возможностью отмены"""

    async with aiohttp.ClientSession() as session:
        payload = {"prompt": prompt}
        if session_id:
            payload["session_id"] = session_id

        try:
            async with session.post(
                    f"{BACKEND_URL}/generate",
                    json=payload,
                    timeout=300
            ) as response:
                result = await response.json()

                if result.get("session_id"):
                    cl.user_session.set("session_id", result["session_id"])

                if result["status"] == "success":
                    await handle_success(result["code"], chat_history, msg)

                elif result["status"] == "need_info":
                    await handle_need_info(result["question"], chat_history, msg)

                elif result["status"] == "error":
                    await handle_error(result.get("message", "Неизвестная ошибка"), msg)

        except aiohttp.ClientError as e:
            await msg.update()
            await cl.Message(content=f"❌ Ошибка соединения с бэкендом: {str(e)}").send()
        except asyncio.CancelledError:
            await cancel_backend_generation(session_id)
            raise
        except Exception as e:
            await msg.update()
            await cl.Message(content=f"❌ Непредвиденная ошибка: {str(e)}").send()


async def cancel_backend_generation(session_id: str):
    """Отправляет запрос на отмену генерации на бэкенд"""
    if not session_id:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"{BACKEND_URL}/cancel",
                    json={"session_id": session_id},
                    timeout=5
            ) as response:
                await response.json()
    except Exception:
        pass


async def handle_success(code: str, chat_history: list, msg: cl.Message):
    """Отображает успешно сгенерированный Lua-код"""
    await msg.stream_token("✅ **Сгенерированный Lua-код:**\n\n")

    formatted_code = f"```lua\n{code}\n```"
    for chunk in split_chunks(formatted_code, 10):
        await msg.stream_token(chunk)
        await asyncio.sleep(0.02)

    await msg.update()
    chat_history.append({"role": "assistant", "content": code})


async def handle_need_info(question: str, chat_history: list, msg: cl.Message):
    """Отображает уточняющий вопрос"""
    content = f"🤔 **Уточнение:**\n\n{question}\n\n*Пожалуйста, ответь на вопрос.*"
    await msg.stream_token(content)
    await msg.update()
    chat_history.append({"role": "assistant", "content": f"[QUESTION] {question}"})


async def handle_error(error_msg: str, msg: cl.Message):
    """Отображает ошибку"""
    content = f"❌ **Ошибка генерации:**\n\n{error_msg}"
    await msg.stream_token(content)
    await msg.update()


def split_chunks(text: str, chunk_size: int):
    """Генератор для разбивки текста на чанки"""
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]


@cl.action_callback("cancel_generation")
async def on_cancel_action(action: cl.Action):
    """Отмена текущей генерации"""
    task = cl.user_session.get("current_task")

    if task and not task.done():
        task.cancel()
        await cl.Message(content="⏹️ **Отмена генерации...**").send()
    else:
        await cl.Message(content="ℹ️ Нет активной генерации для отмены.").send()


@cl.action_callback("reset_session")
async def on_reset_action(action: cl.Action):
    """Сброс сессии"""
    task = cl.user_session.get("current_task")
    if task and not task.done():
        task.cancel()

    session_id = cl.user_session.get("session_id")

    if session_id:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                        f"{BACKEND_URL}/reset",
                        json={"session_id": session_id},
                        timeout=5
                ) as response:
                    await response.json()
            except Exception:
                pass

    cl.user_session.set("session_id", None)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("current_task", None)

    await cl.Message(content="🔄 **Сессия сброшена. Можем начать заново!**").send()


@cl.on_stop
async def on_stop():
    """Вызывается при остановке генерации пользователем"""
    task = cl.user_session.get("current_task")
    if task and not task.done():
        task.cancel()

        session_id = cl.user_session.get("session_id")
        await cancel_backend_generation(session_id)


@cl.on_settings_update
async def setup_actions():
    """Настройка кнопок в интерфейсе"""
    await cl.Action(
        name="cancel_generation",
        value="cancel",
        label="⏹️ Отменить генерацию",
        description="Остановить текущую генерацию"
    ).send()

    await cl.Action(
        name="reset_session",
        value="reset",
        label="🔄 Сбросить сессию",
        description="Начать новый диалог"
    ).send()