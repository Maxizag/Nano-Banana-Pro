import asyncio
from aiogram import Bot
from app import config

# Если config.py нет, раскомментируй строку ниже и вставь ID
# ADMIN_CHANNEL_ID = -100xxxxxxxxxx

async def send_log(bot: Bot, text: str, disable_notification: bool = False):
    """Базовая функция отправки текста в канал"""
    try:
        await bot.send_message(
            chat_id=config.ADMIN_CHANNEL_ID,
            text=text,
            parse_mode="HTML",
            disable_notification=disable_notification
        )
    except Exception as e:
        print(f"⚠️ Ошибка логгера: {e}")

async def send_photo_log(bot: Bot, photo, caption: str):
    """Отправка фото-отчета (для генераций)"""
    try:
        await bot.send_photo(
            chat_id=config.ADMIN_CHANNEL_ID,
            photo=photo,
            caption=caption,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"⚠️ Ошибка логгера (фото): {e}")

# 🟢 ТИП 1: НОВЫЙ ПОЛЬЗОВАТЕЛЬ
async def log_new_user(bot: Bot, user, deep_link: str = None):
    link_info = deep_link if deep_link else "Органика"
    username = f"@{user.username}" if user.username else "Нет"
    
    text = (
        "👤 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ</b>\n"
        "➖➖➖➖➖➖➖\n"
        f"Имя: <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
        f"Username: {username}\n"
        f"ID: <code>{user.id}</code>\n"
        f"Источник: {link_info}\n"
        "#new_user"
    )
    # Запускаем в фоне, чтобы не тормозить бота
    asyncio.create_task(send_log(bot, text))

# 💰 ТИП 2: ФИНАНСЫ
async def log_payment(bot: Bot, user, amount: int, item_name: str, new_balance: int):
    username = f"@{user.username}" if user.username else "Нет"
    text = (
        "💸 <b>УСПЕШНАЯ ОПЛАТА</b>\n"
        "➖➖➖➖➖➖➖\n"
        f"Кто: {username} (<a href='tg://user?id={user.id}'>Ссылка</a>)\n"
        f"Сумма: <b>{amount} RUB</b>\n"
        f"Товар: {item_name}\n"
        f"Баланс после: {new_balance} 🍌\n"
        "#payment"
    )
    asyncio.create_task(send_log(bot, text))

# 🎨 ТИП 3: ГЕНЕРАЦИЯ
async def log_generation(bot: Bot, user, prompt: str, model: str, photo_file_id: str):
    username = f"@{user.username}" if user.username else "Нет"
    caption = (
        "🎨 <b>Генерация</b>\n"
        f"Юзер: {username}\n"
        f"Модель: {model}\n"
        f"Промпт: <code>{prompt}</code>\n"
        "#generation"
    )
    asyncio.create_task(send_photo_log(bot, photo_file_id, caption))

# 👣 ТИП 4: ДЕЙСТВИЯ (Без звука)
async def log_action(bot: Bot, user_id: int, username: str, action: str, is_message: bool = False):
    u_name = f"@{username}" if username else f"ID:{user_id}"
    act_type = "💬 Сообщение" if is_message else "👣 Действие"
    tag = "#message" if is_message else "#action"
    
    text = (
        f"{act_type}: {action}\n"
        f"Юзер: {u_name}\n"
        f"{tag}"
    )
    asyncio.create_task(send_log(bot, text, disable_notification=True))

# ⚠️ ТИП 5: ОШИБКИ
async def log_error(bot: Bot, user_id: int, username: str, prompt: str, error_text: str):
    u_name = f"@{username}" if username else f"ID:{user_id}"
    text = (
        "🚨 <b>ОШИБКА / СБОЙ</b>\n"
        f"Юзер: {u_name}\n"
        f"Запрос: <code>{prompt}</code>\n"
        f"Статус: {error_text}\n"
        "#error"
    )
    asyncio.create_task(send_log(bot, text))