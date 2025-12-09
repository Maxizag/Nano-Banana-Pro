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
        
    # Заглушка ссылки
    link = f"https://t.me/nanobanan_promt" 
    emo = package['emoji'] if package['emoji'] else "🍌"
    
    text = (f"⚡ *Отличный выбор!*\n\nБаланс: +*{package['gens']} {package['suffix']}* {emo}\n💳 К оплате: *{package['price']}₽*\n\n⏳ _Бананы зачислим сразу после оплаты._")
    
    b = InlineKeyboardBuilder()
    b.button(text=f"💳 Оплатить {package['price']}₽", url=link)
    b.button(text="🔙 Другой тариф", callback_data="goto_shop")
    b.adjust(1)
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

@router.message(F.text == "👤 Профиль") 
@router.message(Command("profile"))
async def show_profile(message: types.Message):
    async with async_session() as session: data = await get_user_profile_data(session, message.from_user.id)
    if not data: await message.answer("Ошибка."); return
    
    user = data['user']
    reg = user.created_at.strftime("%d.%m.%Y")
    
    text = (f"👤 *Твой профиль*\n\n🍌 Баланс: *{user.generations_balance}*\n🎨 Артов: *{user.total_generations_used}*\n📅 Регистрация: *{reg}*")
    
    b = InlineKeyboardBuilder()
    b.button(text="🍌 Купить бананы", callback_data="goto_shop")
    b.button(text="🎁 Получить бесплатно", callback_data="goto_free")
    b.adjust(1)
    
    await message.answer(text, parse_mode="Markdown", reply_markup=b.as_markup())

@router.message(F.text.contains("Гайд")) 
async def cmd_guide(message: types.Message):
    await message.answer("📚 *Гайд по Nano Banana*\n\n1. **Текст в картинку**: Просто напиши, что хочешь увидеть.\n2. **Фото + Текст**: Пришли фото и подпиши.\n3. **Замена**: Нажми «Начать творить» -> «Заменить объект».\n\n💡 *Совет:* Для лучших результатов используй PRO режим.", parse_mode="Markdown")

# --- ДОП КОЛБЕКИ ---
@router.callback_query(F.data == "goto_shop")
async def cb_goto_shop(c: types.CallbackQuery): await c.answer(); await cmd_shop(c.message)

@router.callback_query(F.data == "goto_free")
async def cb_goto_free(c: types.CallbackQuery, bot: Bot): 
    await c.answer()
    await show_freebies(c.message, bot)