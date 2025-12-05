from aiogram import Router, types, F, Bot, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.config import ADMIN_IDS
from app.database import async_session
from app.services.user_service import get_bot_stats, find_user_by_input, admin_change_balance
from app.services.payment_service import confirm_purchase

router = Router()


# --- СОСТОЯНИЯ АДМИНА ---
class AdminState(StatesGroup):
    waiting_for_user_search = State() # Ждем ввода ID или @ника
    waiting_for_balance_change = State() # Ждем сумму для начисления
    waiting_for_message = State() # Ждем текст сообщения юзеру

# --- ГЛАВНОЕ МЕНЮ АДМИНА ---
@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return

    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="🔍 Найти пользователя", callback_data="admin_find_user")
    builder.adjust(1)

    await message.answer("👑 **Панель Администратора**", reply_markup=builder.as_markup(), parse_mode="Markdown")

# --- СТАТИСТИКА ---
@router.callback_query(F.data == "admin_stats")
async def cb_stats(callback: types.CallbackQuery):
    async with async_session() as session:
        stats = await get_bot_stats(session)

    text = (
        "📊 **Статистика Бота**\n\n"
        f"👥 Людей: **{stats['users']}**\n"
        f"🎨 Генераций: **{stats['gens']}**\n"
        f"💰 Касса: **{stats['money']}₽**"
    )
    # Кнопка "Назад"
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Меню", callback_data="admin_menu")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# --- ВОЗВРАТ В МЕНЮ ---
@router.callback_query(F.data == "admin_menu")
async def cb_back_admin(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_admin(callback.message)

# =====================================================================
# ПОИСК ПОЛЬЗОВАТЕЛЯ
# =====================================================================

@router.callback_query(F.data == "admin_find_user")
async def cb_find_user(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.waiting_for_user_search)
    await callback.message.answer("🔍 **Введите ID пользователя или @username:**")
    await callback.answer()

@router.message(AdminState.waiting_for_user_search)
async def process_find_user(message: types.Message, state: FSMContext):
    user_input = message.text
    
    async with async_session() as session:
        user = await find_user_by_input(session, user_input)
    
    if not user:
        await message.answer("❌ Пользователь не найден. Попробуй еще раз или жми /admin")
        return

    # Запоминаем ID найденного юзера в памяти админа
    await state.update_data(target_user_id=user.telegram_id)
    await state.clear() # Сбрасываем состояние поиска

    # Рисуем карточку
    await show_user_card(message, user.telegram_id, user.full_name, user.username, user.generations_balance)


async def show_user_card(message: types.Message, user_id, name, username, balance):
    # Используем HTML для безопасности
    # html.quote(str(name)) защитит от имен типа "<b>Hack</b>"
    
    safe_name = html.quote(str(name))
    safe_username = html.quote(str(username)) if username else "Нет"
    
    text = (
        f"👤 <b>Карточка пользователя</b>\n"
        f"🆔 <code>{user_id}</code>\n"
        f"👤 Имя: {safe_name}\n"
        f"🔗 Ник: @{safe_username}\n\n"
        f"💎 <b>Баланс: {balance}</b>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить", callback_data=f"adm_add_{user_id}")
    builder.button(text="➖ Отнять", callback_data=f"adm_rem_{user_id}")
    builder.button(text="✉️ Написать", callback_data=f"adm_msg_{user_id}")
    builder.button(text="🔙 Меню", callback_data="admin_menu")
    builder.adjust(2, 1, 1)
    
    # ВАЖНО: parse_mode="HTML"
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# =====================================================================
# УПРАВЛЕНИЕ БАЛАНСОМ
# =====================================================================

@router.callback_query(F.data.startswith("adm_add_") | F.data.startswith("adm_rem_"))
async def cb_change_balance(callback: types.CallbackQuery, state: FSMContext):
    action, user_id = callback.data.split("_")[1], int(callback.data.split("_")[2])
    
    # Запоминаем, что и кому делаем
    await state.update_data(target_user_id=user_id, action_type=action)
    await state.set_state(AdminState.waiting_for_balance_change)
    
    op_text = "начислить" if action == "add" else "списать"
    await callback.message.answer(f"🔢 Введи число, сколько генераций {op_text}:")
    await callback.answer()

@router.message(AdminState.waiting_for_balance_change)
async def process_balance_change(message: types.Message, state: FSMContext, bot: Bot):
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введи целое число!")
        return

    data = await state.get_data()
    target_id = data['target_user_id']
    action = data['action_type']
    
    # Если action == "rem", делаем число отрицательным
    final_amount = amount if action == "add" else -amount
    
    async with async_session() as session:
        new_balance = await admin_change_balance(session, target_id, final_amount)
    
    if new_balance is not None:
        await message.answer(f"✅ Баланс изменен! Новый баланс: **{new_balance}**")
        
        # Уведомляем юзера (это очень полезно для саппорта!)
        try:
            if action == "add":
                msg = f"🎁 **Администратор начислил вам {amount} генераций!**\nПриятного творчества! 🍌"
                await bot.send_message(target_id, msg, parse_mode="Markdown")
        except:
            await message.answer("⚠️ Юзеру не удалось отправить уведомление (блок бота).")
    else:
        await message.answer("❌ Ошибка базы данных.")
    
    await state.clear()
    await cmd_admin(message) # Возвращаем в меню

# =====================================================================
# ОТПРАВКА СООБЩЕНИЯ (Support)
# =====================================================================

@router.callback_query(F.data.startswith("adm_msg_"))
async def cb_send_msg(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminState.waiting_for_message)
    
    await callback.message.answer("✍️ **Введите текст сообщения для пользователя:**")
    await callback.answer()

@router.message(AdminState.waiting_for_message)
async def process_send_msg(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id = data['target_user_id']
    
    try:
        # Шлем от лица бота
        await bot.send_message(
            chat_id=target_id, 
            text=f"📨 **Сообщение от поддержки:**\n\n{message.text}", 
            parse_mode="Markdown"
        )
        await message.answer("✅ Сообщение отправлено!")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")
        
    await state.clear()
    await cmd_admin(message)

# =====================================================================
# ПОДТВЕРЖДЕНИЕ ПЛАТЕЖА (ОСТАВЛЯЕМ СТАРУЮ КОМАНДУ ТОЖЕ)
# =====================================================================
@router.message(Command("confirm_pay"))
async def cmd_confirm_pay(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        order_id = int(message.text.split()[1])
    except:
        await message.answer("Пиши ID: `/confirm_pay 1`")
        return

    async with async_session() as session:
        success = await confirm_purchase(session, order_id)
    
    if success:
        await message.answer(f"✅ Заказ #{order_id} проведен.")
    else:
        await message.answer("❌ Ошибка заказа.")