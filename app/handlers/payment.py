from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.database import async_session
from app.services.user_service import get_user_profile_data, claim_subscription_bonus
from app.services.payment_service import create_purchase_record
from app import config

router = Router()

# 👇👇👇 ВСТАВЬ СЮДА СВОИ ЮЗЕРНЕЙМЫ 👇👇👇
CHANNEL_ID = "@nanobanan_promt"
CHAT_ID = "@nanabanan_chat"

PACKAGES = {
    "mini": {"name": "Start", "gens": 8, "price": 79, "emoji": "", "suffix": "бананов"},
    "standard": {"name": "Medium", "gens": 44, "price": 299, "emoji": "", "suffix": "банана"},
    "large": {"name": "Big", "gens": 140, "price": 699, "emoji": "🔥", "suffix": "бананов"},
    "xl": {"name": "Mega", "gens": 340, "price": 1499, "emoji": "", "suffix": "бананов"},
    "whale": {"name": "Whale", "gens": 832, "price": 3499, "emoji": "👑", "suffix": "банана"},
}

# =====================================================================
# 🎁 РАЗДЕЛ ХАЛЯВЫ (Обновленный текст)
# =====================================================================
@router.message(F.text == "🎁 Бесплатно🍌🍌")
async def show_freebies(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    bot_info = await bot.me()
    
    # Формируем ссылку динамически, чтобы работало при смене юзернейма бота
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    # 👇 НОВЫЙ КОМПАКТНЫЙ ТЕКСТ
    text = (
        "<b>Пополни баланс без денег!</b>\n"
        "Забирай бананы за простые действия:\n\n"
        "1️⃣ <b>Зови друзей (+2 🍌 за каждого)</b>\n"
        "Количество не ограничено!\n"
        "🔗 Твоя ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        "2️⃣ <b>Подпишись на наш канал и чат (+1 🍌 за каждый)</b>\n"
        "Жми на кнопки ниже 👇"
    )
    
    builder = InlineKeyboardBuilder()
    
    # Ссылки формируем из ID (убираем @ для url)
    c_link = f"https://t.me/{CHANNEL_ID.replace('@', '')}"
    chat_link = f"https://t.me/{CHAT_ID.replace('@', '')}"
    
    # Ряд 1: Канал
    builder.button(text="📢 Канал", url=c_link)
    builder.button(text="✅ Проверить (+1🍌)", callback_data="check_channel")
    
    # Ряд 2: Чат
    builder.button(text="💬 Чат", url=chat_link)
    builder.button(text="✅ Проверить (+1🍌)", callback_data="check_chat")
    
    builder.adjust(2, 2)
    
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

# --- ПРОВЕРКИ ---
@router.callback_query(F.data == "check_channel")
async def cb_check_channel(callback: types.CallbackQuery, bot: Bot):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, callback.from_user.id)
        if m.status in ["left", "kicked"]: raise Exception
    except: await callback.answer("❌ Сначала подпишись!", show_alert=True); return

    async with async_session() as session:
        if await claim_subscription_bonus(session, callback.from_user.id, 'channel', 1):
            await callback.answer("🎉 +1 банан начислен!", show_alert=True)
        else: await callback.answer("🍌 Уже получено!", show_alert=True)

@router.callback_query(F.data == "check_chat")
async def cb_check_chat(callback: types.CallbackQuery, bot: Bot):
    try:
        m = await bot.get_chat_member(CHAT_ID, callback.from_user.id)
        if m.status in ["left", "kicked"]: raise Exception
    except: await callback.answer("❌ Сначала вступи!", show_alert=True); return

    async with async_session() as session:
        if await claim_subscription_bonus(session, callback.from_user.id, 'chat', 1):
            await callback.answer("🎉 +1 банан начислен!", show_alert=True)
        else: await callback.answer("🍌 Уже получено!", show_alert=True)

# =====================================================================
# 💰 МАГАЗИН И ПРОФИЛЬ
# =====================================================================
@router.message(F.text == "🍌 Купить бананы")
@router.message(Command("buy"))
async def cmd_shop(message: types.Message):
    builder = InlineKeyboardBuilder()
    for key, pkg in PACKAGES.items():
        # Расчет цены за 1 шт
        p = pkg['price'] / pkg['gens']
        s = f"{p:.2f}".replace('.', ',').rstrip('0').rstrip(',')
        if s.endswith(','): s = s[:-1]
        
        btn = f"{pkg['emoji']}{pkg['gens']} {pkg['suffix']} - {pkg['price']}₽ | {s}₽/🍌"
        builder.button(text=btn, callback_data=f"buy_{key}")
    builder.adjust(1)
    await message.answer(
        "🍌 *Магазин Бананов*\n\nПополни баланс и твори без ограничений!\n\n*Стоимость:*\n🍌 Standard: 1 банан\n💎 PRO: 4 банана\n\nВыбери пакет👇",
        reply_markup=builder.as_markup(), parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("buy_"))
async def cb_buy_package(callback: types.CallbackQuery):
    pkg_key = callback.data.split("_")[1]
    package = PACKAGES.get(pkg_key)
    if not package: await callback.answer("Тариф не найден"); return
    
    user_id = callback.from_user.id
    async with async_session() as session:
        purchase = await create_purchase_record(session, user_id, package['price'], package['gens'])
        
# ... (выше идет создание purchase) ...

    # Ссылка на оплату (заглушка)
    fake_payment_link = f"https://t.me/nanobanana_ai" 
    
    # 👇 НОВЫЙ ТЕКСТ (HTML)
    text = (
        "⚡ <b>Отличный выбор!</b>\n\n"
        f"🍌 Пополнение: <b>+{package['gens']} {package['suffix']}</b>\n"
        f"💳 К оплате: <b>{package['price']}₽</b>\n\n"
        "⏳ <i>Бананы зачислим сразу после оплаты.</i>\n\n"
        "📄 Оплачивая, вы принимаете условия <a href='https://telegra.ph/PUBLICHNAYA-OFERTA-12-09-5'>Оферты</a>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"💳 Оплатить {package['price']}₽", url=fake_payment_link)
    builder.button(text="🔙 Другой тариф", callback_data="goto_shop")
    builder.adjust(1)
    
    # ⚠️ ВАЖНО: parse_mode="HTML" и disable_web_page_preview=True (чтобы ссылка не разворачивалась в картинку)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML", disable_web_page_preview=True)

@router.message(F.text == "👤 Профиль") 
@router.message(Command("profile"))
async def show_profile(message: types.Message):
    """
    Профиль пользователя (Clean UI по ТЗ)
    - Показывает ID, баланс, счетчик шедевров
    - 3 кнопки: Купить, Заработать, Техподдержка
    """
    user_id = message.from_user.id
    
    async with async_session() as session:
        data = await get_user_profile_data(session, user_id)
    
    if not data:
        await message.answer("❌ Ошибка загрузки профиля.")
        return
    
    user = data['user']
    
    # 📝 ТЕКСТ ПО ТЗ (HTML разметка для моноширинного ID)
    text = (
        "👤 <b>Твой профиль</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"🍌 Баланс: <b>{user.generations_balance} шт.</b>\n"
        f"🎨 Создано шедевров: <b>{user.total_generations_used}</b>\n\n"
        "👇 <b>Управление аккаунтом:</b>"
    )
    
    # ⌨️ КНОПКИ ПО ТЗ (3 ряда)
    builder = InlineKeyboardBuilder()
    
    # Ряд 1: Монетизация
    builder.button(text="🍌 КУПИТЬ БАНАНЫ", callback_data="goto_shop")
    
    # Ряд 2: Удержание
    builder.button(text="⚒️ Заработать бананы", callback_data="goto_free")
    
    # Ряд 3: Доверие (URL-кнопка)
    builder.button(text="👨‍💻 Техподдержка", url="https://t.me/nan0banana_help")
    
    builder.adjust(1)  # Каждая кнопка на новой строке
    
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

# 👇 ЗАМЕНИТЬ ФУНКЦИЮ cmd_guide НА ЭТУ 👇

@router.message(F.text == "ℹ️ О нас") 
async def cmd_about(message: types.Message):
    text = (
        "ℹ️ <b>О сервисе Nano Banana Pro</b>\n"
        "Сервис предоставляет доступ к облачной генерации изображений с помощью нейросети.\n"
        "🍌 <b>Бананы</b> — это внутренняя валюта, которая используется для оплаты генераций.\n\n"
        
        "👤 <b>Владелец сервиса:</b>\n"
        "Кузьмичева Диана Юрьевна\n"
        "📄 <b>Юридический статус:</b>\n"
        "Самозанятый (Плательщик НПД)\n"
        "🆔 <b>ИНН:</b> 025502709811\n\n"
        
        "📞 <b>Контакты:</b>\n"
        "Telegram: @nan0banana_help\n"
        "Email: help.nanobanan@gmail.com\n\n"
        
        "⚖️ <b>Документы:</b>\n"
        "• <a href='https://telegra.ph/PUBLICHNAYA-OFERTA-12-09-5'>Договор-оферта</a>\n"
        "• <a href='https://telegra.ph/POLITIKA-V-OTNOSHENII-OBRABOTKI-PERSONALNYH-DANNYH-12-09-5'>Политика конфиденциальности</a>"
    )
    # disable_web_page_preview=True чтобы не вылезала превьюшка телеграфа
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

@router.callback_query(F.data == "goto_shop")
async def cb_goto_shop(callback: types.CallbackQuery):
    await callback.answer()
    # Вызываем функцию магазина (она выше в этом же файле)
    await cmd_shop(callback.message)

@router.callback_query(F.data == "goto_free")
async def cb_goto_free(callback: types.CallbackQuery, bot: Bot):
    await callback.answer()
    # Вызываем функцию с заданиями (она тоже в этом файле)
    await show_freebies(callback.message, bot)