import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.database import engine, Base
from app.handlers import start, generation, payment, menu_actions, admin
from app.middlewares.album import AlbumMiddleware # <--- ИМПОРТ
from app import config

async def main():
    logging.basicConfig(level=logging.INFO)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    # 👇 ВАЖНО: Middleware подключаем ПЕРВЫМ!
    dp.message.middleware(AlbumMiddleware(latency=0.8)) # Можно чуть уменьшить latency, если 1.0 долго

    # 👇 Потом роутеры
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(payment.router)
    dp.include_router(menu_actions.router)
    dp.include_router(generation.router)

    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())