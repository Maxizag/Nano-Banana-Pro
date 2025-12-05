import asyncio
from typing import Any, Callable, Dict, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.8): # Ставим 0.8 сек - золотая середина
        self.latency = latency
        self.album_data = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if not event.media_group_id:
            return await handler(event, data)

        group_id = event.media_group_id

        if group_id not in self.album_data:
            self.album_data[group_id] = []
            self.album_data[group_id].append(event)
            await asyncio.sleep(self.latency)

            # Если после сна в списке есть сообщения - обрабатываем их
            if group_id in self.album_data:
                album_messages = self.album_data[group_id]
                album_messages.sort(key=lambda x: x.message_id)
                data["album"] = album_messages
                del self.album_data[group_id]
                return await handler(event, data)
        else:
            self.album_data[group_id].append(event)
            return