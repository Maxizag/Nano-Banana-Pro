from aiogram import Router, types, F, Bot
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.database import async_session
from app.services.user_service import get_user_profile_data, claim_subscription_bonus, admin_change_balance, get_user_balance
from app.services.payment_service import create_purchase_record
from app import config
from app.services.payment_api import create_yoo_payment, check_yoo_payment
from app.services.admin_logger import log_payment


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

# Stars пакеты
STARS_PACKAGES = {
    "stars_4": {"bananas": 4, "stars": 35, "emoji": "🍌"},
    "stars_12": {"bananas": 12, "stars": 90, "emoji": "🍌"},
    "stars_24": {"bananas": 24, "stars": 160, "emoji": "🍌"},
    "stars_60": {"bananas": 60, "stars": 350, "emoji": "🍌"},
    "stars_120": {"bananas": 120, "stars": 650, "emoji": "🍌"},
}

def get_banana_suffix(count):
    """Возвращает правильное окончание для слова 'банан'"""
    if count % 10 == 1 and count % 100 != 11:
        return "банан"
    elif count % 10 in [2, 3, 4] and count % 100 not in [12, 13, 14]:
        return "банана"
    else:
        return "бананов"

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
    
    # Рублевые пакеты
    for key, pkg in PACKAGES.items():
        # Расчет цены за 1 шт
        p = pkg['price'] / pkg['gens']
        s = f"{p:.2f}".replace('.', ',').rstrip('0').rstrip(',')
        if s.endswith(','): s = s[:-1]
        
        btn = f"{pkg['emoji']}{pkg['gens']} {pkg['suffix']} - {pkg['price']}₽ | {s}₽/🍌"
        builder.button(text=btn, callback_data=f"buy_{key}")
    
    # Кнопка перехода на Stars
    builder.button(text="⭐️ Оплатить Stars", callback_data="open_stars_menu")
    
    builder.adjust(1)
    await message.answer(
        "🍌 *Магазин Бананов*\n\nПополни баланс и твори без ограничений!\n\n*Стоимость:*\n🍌 Standard: 1 банан\n💎 PRO: 4 банана\n\nВыбери пакет👇",
        reply_markup=builder.as_markup(), parse_mode="Markdown"
    )

# Меню Stars
@router.callback_query(F.data == "open_stars_menu")
async def show_stars_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    
    for key, pkg in STARS_PACKAGES.items():
        suffix = get_banana_suffix(pkg['bananas'])
        btn_text = f"{pkg['emoji']} {pkg['bananas']} {suffix} — {pkg['stars']} ⭐️"
        builder.button(text=btn_text, callback_data=f"buy_{key}")
    
    builder.button(text="🔙 Назад к рублям", callback_data="open_rub_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⭐️ *Оплата Telegram Stars*\n\nВыбери пакет:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

# Возврат к рублевому меню
@router.callback_query(F.data == "open_rub_menu")
async def back_to_rub_menu(callback: types.CallbackQuery):
    await callback.answer()
    await cmd_shop(callback.message)

# =====================================================================
# 2. ОФОРМЛЕНИЕ (ТЕКСТ + ССЫЛКА НА ЮКАССУ)
# =====================================================================
@router.callback_query(F.data.startswith("buy_"))
async def cb_buy_package(callback: types.CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    
    # Проверяем, это Stars пакет или рублевый
    if len(parts) >= 3 and parts[1] == "stars":
        # STARS ЛОГИКА
        pkg_key = f"{parts[1]}_{parts[2]}"  # stars_4, stars_12 и т.д.
        await handle_stars_purchase(callback, bot, pkg_key)
        return
    
    # РУБЛИ ЛОГИКА (старая)
    pkg_key = parts[1]
    package = PACKAGES.get(pkg_key)
    if not package: 
        await callback.answer("Тариф не найден")
        return
    
    user_id = callback.from_user.id
    
    async with async_session() as session:
        await create_purchase_record(session, user_id, package['price'], package['gens'])

    try:
        desc = f"Покупка {package['gens']} бананов (ID: {user_id})"
        payment = create_yoo_payment(package['price'], desc, user_id)
        pay_url = payment.confirmation.confirmation_url
        payment_id = payment.id

        text = (
            "⚡ <b>Отличный выбор!</b>\n\n"
            f"🍌 Пополнение: <b>+{package['gens']} {package['suffix']}</b>\n"
            f"💳 К оплате: <b>{package['price']}₽</b>\n\n"
            "⏳ <i>Бананы зачислим сразу после оплаты.</i>\n\n"
            "📄 Оплачивая, вы принимаете условия <a href='https://telegra.ph/PUBLICHNAYA-OFERTA-12-09-5'>Оферты</a>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text=f"💳 Оплатить {package['price']}₽", url=pay_url)
        builder.button(text="✅ Я оплатил", callback_data=f"check_{payment_id}_{pkg_key}")
        builder.button(text="🔙 Отмена", callback_data="goto_shop")
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML", disable_web_page_preview=True)
        
    except Exception as e:
        print(f"YooKassa Error: {e}")
        await callback.answer("Ошибка создания ссылки. Попробуйте позже.", show_alert=True)

# Создание Stars инвойса
async def handle_stars_purchase(callback: types.CallbackQuery, bot: Bot, pkg_key: str):
    package = STARS_PACKAGES.get(pkg_key)
    if not package:
        await callback.answer("Пакет не найден")
        return
    
    user_id = callback.from_user.id
    suffix = get_banana_suffix(package['bananas'])
    
    # Формируем payload для идентификации платежа
    payload = f"{pkg_key}_{user_id}"
    
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"{package['bananas']} {suffix}",
        description=f"Пополнение баланса на {package['bananas']} {suffix}",
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=f"{package['bananas']} {suffix}", amount=package['stars'])],
        provider_token=""  # Для Stars пустой
    )
    
    await callback.answer()

# =====================================================================
# 3. ПРОВЕРКА ПЛАТЕЖА (ПО КНОПКЕ)
# =====================================================================
@router.callback_query(F.data.startswith("check_"))
async def cb_check_payment(callback: types.CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    payment_id = parts[1]
    pkg_key = parts[2]
    package = PACKAGES.get(pkg_key)
    if not package: return

    try:
        # Проверяем статус в ЮКассе через API
        status = check_yoo_payment(payment_id)
        
        if status == "succeeded":
            async with async_session() as session:
                # Начисляем
                await admin_change_balance(session, callback.from_user.id, package['gens'])
                # Логируем
                try:
                    new_bal = await get_user_balance(session, callback.from_user.id)
                    await log_payment(bot, callback.from_user, package['price'], f"{package['gens']} Бананов", new_bal)
                except: pass

            # Поздравляем
            await callback.message.edit_text(
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"🍌 Начислено: <b>+{package['gens']} бананов</b>\n"
                f"Спасибо за покупку! Можно снова творить 🎨",
                parse_mode="HTML"
            )
            
        elif status == "pending":
            await callback.answer("⏳ Оплата еще не поступила. Завершите платеж в браузере.", show_alert=True)
            
        elif status == "canceled":
            await callback.message.edit_text("❌ Платеж отменен.", reply_markup=None)
            
    except Exception as e:
        print(f"Check Error: {e}")
        await callback.answer("Ошибка проверки.", show_alert=True)

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
        "Тел.: +79953435561\n"
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

# =====================================================================
# ОБРАБОТЧИКИ STARS ПЛАТЕЖЕЙ
# =====================================================================

# Pre-checkout для Stars
@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(
        pre_checkout_query_id=pre_checkout.id,
        ok=True
    )

# Успешная оплата Stars
@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message, bot: Bot):
    payment = message.successful_payment
    payload = payment.invoice_payload
    
    # Извлекаем pkg_key и user_id из payload
    parts = payload.split("_")
    pkg_key = f"{parts[0]}_{parts[1]}"  # stars_4, stars_12 и т.д.
    user_id = int(parts[2])
    
    package = STARS_PACKAGES.get(pkg_key)
    if not package:
        await message.answer("❌ Ошибка обработки платежа")
        return
    
    suffix = get_banana_suffix(package['bananas'])
    
    # Начисляем бананы
    async with async_session() as session:
        await admin_change_balance(session, user_id, package['bananas'])
        
        # Логируем платеж
        try:
            new_bal = await get_user_balance(session, user_id)
            await log_payment(bot, message.from_user, package['stars'], f"{package['bananas']} {suffix} (Stars)", new_bal)
        except:
            pass
    
    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"🍌 Начислено: <b>{package['bananas']} {suffix}</b>\n"
        f"Спасибо за покупку! 🎨",
        parse_mode="HTML"
    )