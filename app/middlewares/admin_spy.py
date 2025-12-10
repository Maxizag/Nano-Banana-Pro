from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from app.services.admin_logger import log_action

class AdminSpyMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        # Получаем объект бота из контекста
        bot = data.get("bot")
        user = event.from_user
        
        # ЛОГИКА ДЛЯ СООБЩЕНИЙ
        if isinstance(event, Message):
            # Логируем только текст и только если это НЕ команда (команды логируются отдельно или не нужны)
            if event.text and not event.text.startswith("/"):
                # Обрезаем длинные сообщения
                safe_text = event.text[:200] + "..." if len(event.text) > 200 else event.text
                await log_action(bot, user.id, user.username, safe_text, is_message=True)

        # ЛОГИКА ДЛЯ КНОПОК (CALLBACK)
        elif isinstance(event, CallbackQuery):
            # Логируем нажатие
            await log_action(bot, user.id, user.username, f"Нажал кнопку [ data={event.data} ]", is_message=False)

        return await handler(event, data)