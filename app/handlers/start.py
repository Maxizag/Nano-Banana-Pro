from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.markdown import hbold, hlink

from app.database import async_session
from app.services.user_service import get_user, create_user, admin_change_balance
from app import config

router = Router()

# =======================================================
# ⚙️ НАСТРОЙКИ
# =======================================================
CHANNEL_LINK = "https://t.me/nanobanan_promt"
WELCOME_PHOTO = "AgACAgIAAxkBAAIGbWky1V4aiUImfckmTzqXjKcykdunAAJqC2sb4L2ZSWGkUXDH06FzAQADAgADeQADNgQ" 

# =======================================================
# 🛠 ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ (СКЛОНЕНИЕ)
# =======================================================
def get_banana_word(n: int) -> str:
    """Возвращает правильное окончание: банан, банана, бананов"""
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return "банан"
    if 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return "банана"
    return "бананов"

# =======================================================
# 🎹 НИЖНЕЕ МЕНЮ (REPLY KEYBOARD)
# =======================================================
def get_main_kb():
    kb = [
        [KeyboardButton(text="✨ Начать творить")],
        [KeyboardButton(text="🍌 Купить бананы"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="Фарминг🍌"), KeyboardButton(text="📚 Гайд")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, input_field_placeholder="Пиши, что создать")

# =======================================================
# 👋 ОБРАБОТЧИК /START
# =======================================================
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    async with async_session() as session:
        user = await get_user(session, user_id)
        
        # -----------------------------------------------------------
        # СЦЕНАРИЙ 1: НОВЫЙ ПОЛЬЗОВАТЕЛЬ
        # -----------------------------------------------------------
        if not user:
            await create_user(session, telegram_id=user_id, username=username, full_name=full_name)
            
            # Начисляем 3 банана бонуса
            bonus = 3
            await admin_change_balance(session, user_id, bonus)
            
            # Склоняем слово
            word = get_banana_word(bonus)
            
            welcome_text = (
                f"👋 Привет! Я *Nano Banana Pro* 🍌 — твой карманный AI-фотошоп.\n\n"
                f"🎁 *Тебе уже начислено {bonus} подарочных {word}*!\n"
                f"💡 Идеи и промпты смотри тут: [Наш Канал]({CHANNEL_LINK})\n\n"
                f"*Я готов творить!*\n"
                f"Напиши, что создать, или пришли *от 1 до 4 фото*, которые нужно изменить или объединить 👇"
            )
            
            try:
                await message.answer_photo(
                    photo=WELCOME_PHOTO,
                    caption=welcome_text,
                    parse_mode="Markdown",
                    reply_markup=get_main_kb()
                )
            except Exception as e:
                print(f"Ошибка фото: {e}")
                await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_kb())

        # -----------------------------------------------------------
        # СЦЕНАРИЙ 2: СТАРЫЙ ПОЛЬЗОВАТЕЛЬ
        # -----------------------------------------------------------
        else:
            balance = user.generations_balance
            
            # 🅾️ СЦЕНАРИЙ В: БАЛАНС 0
            if balance == 0:
                text = (
                    f"👋 *С возвращением!*\n"
                    f"🍌 Твой баланс: *0 бананов*\n\n"
                    f"Напиши, что создать, или пришли *от 1 до 4 фото*, которые нужно изменить или объединить 👇"
                )
            
            # ✅ СЦЕНАРИЙ С: БАЛАНС > 0 (Оставляем как было)
            else:
                word = get_banana_word(balance)
                text = (
                    f"👋 *С возвращением!*\n"
                    f"🍌 Твой баланс: *{balance} {word}*\n\n"
                    f"*Я готов творить!*\n"
                    f"Напиши, что создать, или пришли *от 1 до 4 фото*, которые нужно изменить или объединить 👇"
                )
            
            # Отправляем сообщение (без фото, как ты и просил)
            await message.answer(
                text, 
                parse_mode="Markdown", 
                reply_markup=get_main_kb()
            )