import asyncio
from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram.types import Message

class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.5): 
        # 0.5 - 0.8 сек достаточно. Если интернет плохой, можно 1.0
        self.latency = latency
        self.album_data = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Если это не альбом — пропускаем дальше
        if not event.media_group_id:
            return await handler(event, data)

        group_id = event.media_group_id

        # Если это первое сообщение из пачки
        if group_id not in self.album_data:
            self.album_data[group_id] = []
            self.album_data[group_id].append(event)
            
            # Ждем остальные фото
            await asyncio.sleep(self.latency)

            # После сна проверяем, собрались ли фото
            if group_id in self.album_data:
                album_messages = self.album_data[group_id]
                
                # Сортируем по ID сообщения, чтобы порядок фото был правильным
                album_messages.sort(key=lambda x: x.message_id)
                
                # Передаем список в хендлер через data
                data["album"] = album_messages
                
                # Чистим память
                del self.album_data[group_id]
                
                # Вызываем хендлер (только 1 раз для всей пачки)
                return await handler(event, data)
        
        # Если это 2-е, 3-е фото и т.д. — просто добавляем в список и стопаем
        else:
            self.album_data[group_id].append(event)
            return
