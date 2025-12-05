from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.database import async_session
from app.services.user_service import get_user_profile_data, claim_bonus
from app.services.payment_service import create_purchase_record
from app import config

router = Router()

# 👇 ПАКЕТЫ (Можешь менять цены тут)
PACKAGES = {
    "mini":     {"name": "Start",  "gens": 8,   "price": 79,   "emoji": "",   "suffix": "бананов"},
    "standard": {"name": "Medium", "gens": 44,  "price": 299,  "emoji": "",   "suffix": "банана"},
    "large":    {"name": "Big",    "gens": 140, "price": 699,  "emoji": "🔥", "suffix": "бананов"},
    "xl":       {"name": "Mega",   "gens": 340, "price": 1499, "emoji": "",   "suffix": "бананов"},
    "whale":    {"name": "Whale",  "gens": 832, "price": 3499, "emoji": "👑", "suffix": "банана"},
}

# =====================================================================
# 1. МАГАЗИН
# =====================================================================
@router.message(F.text == "🍌 Купить бананы")
@router.message(Command("buy"))
async def cmd_shop(message: types.Message):
    builder = InlineKeyboardBuilder()
    
    for key, pkg in PACKAGES.items():
        # Считаем цену за 1 банан для красоты
        per_item = pkg['price'] / pkg['gens']
        per_item_str = f"{per_item:.2f}".replace('.', ',').rstrip('0').rstrip(',')
        if per_item_str.endswith(','): per_item_str = per_item_str[:-1]
        
        btn_text = f"{pkg['emoji']}{pkg['gens']} {pkg['suffix']} - {pkg['price']}₽ | {per_item_str}₽/🍌"
        builder.button(text=btn_text, callback_data=f"buy_{key}")
    
    builder.adjust(1)
    
    await message.answer(
        "🍌 *Магазин Бананов*\n\n"
        "Пополни баланс и твори без ограничений!\n\n"
        "*Стоимость генераций:*\n"
        "🍌 *Обычная:* 1 банан\n"
        "💎 *PRO-режим:* 4 банана\n\n"
        "🔥 Чем больше пакет — тем дешевле 1 банан!\n\n"
        "Выбери пакет👇",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

# =====================================================================
# 2. ОФОРМЛЕНИЕ ЗАКАЗА
# =====================================================================
@router.callback_query(F.data.startswith("buy_"))
async def cb_buy_package(callback: types.CallbackQuery):
    pkg_key = callback.data.split("_")[1]
    package = PACKAGES.get(pkg_key)
    
    if not package:
        await callback.answer("Тариф не найден")
        return

    user_id = callback.from_user.id

    async with async_session() as session:
        # Создаем запись о покупке (статус pending)
        purchase = await create_purchase_record(session, user_id, package['price'], package['gens'])
        order_id = purchase.id

    # ⚠️ ТУТ ДОЛЖНА БЫТЬ ССЫЛКА НА ЮКАССУ ИЛИ PAYMENT GATEWAY
    # Пока заглушка
    fake_payment_link = f"https://t.me/nanobanana_ai" 
    
    display_emoji = package['emoji'] if package['emoji'] else "🍌"
    
    text = (
        f"⚡ *Отличный выбор!*\n\n"
        f"Баланс будет пополнен на *{package['gens']} {package['suffix']}* {display_emoji}\n\n"
        f"💳 К оплате: *{package['price']}₽*\n\n"
        "⏳ _Бананы зачислим сразу после оплаты._"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"💳 Оплатить {package['price']}₽", url=fake_payment_link)
    builder.button(text="🔙 Другой тариф", callback_data="goto_shop")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# =====================================================================
# 3. ПРОФИЛЬ
# =====================================================================
# ✅ ИСПРАВЛЕНО: реагируем на новый текст кнопки
@router.message(F.text == "👤 Профиль") 
@router.message(Command("profile"))
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    
    async with async_session() as session:
        data = await get_user_profile_data(session, user_id)
    
    if not data:
        await message.answer("Ошибка получения профиля.")
        return

    user = data['user']
    purchases = data['last_purchases']
    total_spent = data['total_spent']
    reg_date = user.created_at.strftime("%d.%m.%Y")

    text = (
        "👤 *Твой профиль*\n\n"
        f"🍌 Баланс: *{user.generations_balance}*\n"
        f"🎨 Артов: *{user.total_generations_used}*\n"
        f"📅 Регистрация: *{reg_date}*\n"
        f"💳 Потрачено: *{total_spent}₽*\n\n"
    )

    if purchases:
        text += "*История пополнений:*\n"
        for p in purchases:
            p_date = p.created_at.strftime("%d.%m")
            text += f"• +{p.amount}🍌 ({p.price}₽) — {p_date}\n"
    else:
        text += "_Истории покупок пока нет._"

    builder = InlineKeyboardBuilder()
    builder.button(text="🍌 Купить бананы", callback_data="goto_shop")
    # Добавляем кнопку бонуса сюда, раз уж она есть в функционале
    builder.button(text=f"🎁 Забрать бонус (+{config.BONUS_AMOUNT})", callback_data="get_bonus")
    builder.adjust(1)
    
    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# =====================================================================
# 4. НОВЫЕ РАЗДЕЛЫ (Гайд и Фарминг)
# =====================================================================
@router.message(F.text.contains("Гайд")) # "📚 Гайд"
async def cmd_guide(message: types.Message):
    text = (
        "📚 *Гайд по Nano Banana*\n\n"
        "1. **Текст в картинку**: Просто напиши, что хочешь увидеть.\n"
        "   _Пример: Кот в скафандре на Луне_\n\n"
        "2. **Фото + Текст**: Пришли фото и подпиши, что изменить.\n"
        "   _Пример: Сделай его в стиле киберпанк_\n\n"
        "3. **Замена**: Нажми «Начать творить» -> «Заменить объект».\n\n"
        "💡 *Совет:* Используй английский для более точных результатов, но русский я тоже понимаю!"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text.contains("Фарминг")) # "Фарминг🍌"
async def cmd_farming(message: types.Message):
    # Пока ведем на бонус, позже можно прикрутить рефералку
    text = (
        "🍌 *Фарминг Бананов*\n\n"
        "Здесь ты можешь получить бесплатные бананы!\n\n"
        "1. **Ежедневный бонус**: Доступен подписчикам канала.\n"
        "2. **Пригласи друга**: +10 бананов за каждого (скоро).\n"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🎁 Забрать бонус (+{config.BONUS_AMOUNT})", callback_data="get_bonus")
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")


# =====================================================================
# 5. КОЛБЕКИ
# =====================================================================
@router.callback_query(F.data == "goto_shop")
async def cb_profile_buy(callback: types.CallbackQuery):
    await callback.answer()
    await cmd_shop(callback.message)

@router.callback_query(F.data == "get_bonus")
async def cb_get_bonus(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    
    # 1. Проверяем подписку
    try:
        member = await bot.get_chat_member(chat_id=config.CHANNEL_USERNAME, user_id=user_id)
        if member.status not in ["creator", "administrator", "member"]:
            await callback.answer("❌ Сначала подпишись на канал!", show_alert=True)
            await callback.message.answer(
                f"📢 Для получения бонуса нужно подписаться на канал:\n{config.CHANNEL_USERNAME}"
            )
            return
    except Exception as e:
        # Если бот не админ канала или ошибка ID
        print(f"Ошибка проверки подписки: {e}")
        # Можно пропустить проверку, если тестируешь локально
        # pass 

    # 2. Начисляем
    async with async_session() as session:
        success = await claim_bonus(session, user_id, config.BONUS_AMOUNT)
    
    if success:
        await callback.message.answer(f"🎉 Ура! Начислено +{config.BONUS_AMOUNT} бананов!")
        await callback.answer()
    else:
        await callback.answer("🍌 Ты уже забрал этот бонус!", show_alert=True)