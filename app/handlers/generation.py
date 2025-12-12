import json
import io
from PIL import Image
from aiogram import Router, types, F, Bot
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatAction
from aiogram import html
import aiohttp
from app.services.admin_logger import log_generation, log_error

from app.database import async_session
from app.services.user_service import (
    check_and_deduct_balance, get_user_balance, is_user_premium, 
    add_history, clear_history, get_history_message_by_id, get_dialog_context,
    start_generation_task, finish_generation_task, admin_change_balance,
    get_user_model_preference, set_user_model_preference
)
from app.services.ai_engine import generate_image
from app.utils import prompts
from app import config

router = Router()

# 👇 ЗАМЕНИТЬ ВЕСЬ СПИСОК IGNORED_TEXTS НА ЭТОТ:
IGNORED_TEXTS = [
    "✨ Начать творить", "🎨 Создать изображение",
    "📸 Примеры работ", "👤 Профиль", "👤 Мой профиль",
    "🍌 Купить бананы", "Фарминг🍌", "ℹ️ О нас", "ℹ️ Что умеет бот?",
    "/start", "/help", "/admin", "/stats", "/clear"
]

class GenState(StatesGroup):
    waiting_for_category_input = State() 
    waiting_for_caption = State()
    waiting_for_base_image = State()
    waiting_for_ref_image = State()
    waiting_for_replace_object_text = State()
    free_mode = State()
    waiting_for_ratio = State()
    preflight_check = State()
    selecting_ratio = State()
    waiting_for_edit_instruction = State()

# =====================================================================
# 🛠 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================
def smart_compress_image(file_bytes: bytes) -> bytes:
    """Сжимает изображение если > 9.5 МБ"""
    LIMIT_BYTES = 9.5 * 1024 * 1024 
    
    if len(file_bytes) <= LIMIT_BYTES:
        return file_bytes 
    
    print(f"⚠️ Файл слишком большой ({len(file_bytes) / 1024 / 1024:.2f} MB). Сжимаю...")
    
    try:
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert("RGB")
            
        max_dimension = 2560
        if max(img.size) > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
        output_io = io.BytesIO()
        img.save(output_io, format='JPEG', quality=85, optimize=True)
        return output_io.getvalue()
    except Exception as e:
        print(f"❌ Ошибка сжатия: {e}")
        return file_bytes

def normalize_image_urls(image_urls) -> list:
    """✅ ЕДИНАЯ функция нормализации URL"""
    if not image_urls:
        return []
    if isinstance(image_urls, str):
        return [image_urls]
    if isinstance(image_urls, list):
        return image_urls
    return []

async def get_photo_url(bot: Bot, file_id: str) -> str:
    """Получает URL фото"""
    if not file_id:
        return None
    file_info = await bot.get_file(file_id)
    return f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"

# =====================================================================
# 🎛 КЛАВИАТУРЫ
# =====================================================================
def get_no_balance_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Купить бананы", callback_data="goto_shop")
    builder.button(text="🎁 Получить бесплатно", callback_data="goto_free")
    builder.adjust(1)
    return builder.as_markup()

def get_preflight_kb(model_type: str, ratio: str, quality: str):
    builder = InlineKeyboardBuilder()
    
    model_btn = "💎 Модель: PRO" if model_type == "pro" else "🍌 Модель: Standard"
    builder.button(text=model_btn, callback_data="pf_toggle_model")
    builder.button(text=f"📐 Формат: {ratio}", callback_data="pf_select_ratio")
    
    if model_type == "pro":
        # Логика подписи кнопки
        if quality == "4k":
            qual_btn = "👑 Качество: 4K"
        elif quality == "2k":
            qual_btn = "🌟 Качество: 2K"
        else:
            qual_btn = "⚡️ Качество: HD"
            
        builder.button(text=qual_btn, callback_data="pf_toggle_quality")
    
    cost = config.COST_PRO if model_type == "pro" else config.COST_STANDARD
    builder.button(text=f"🚀 Сгенерировать ({cost}🍌)", callback_data="pf_start")
    
    builder.adjust(2, 1, 1) if model_type == "pro" else builder.adjust(2, 1)
    return builder.as_markup()

def get_ratio_kb():
    builder = InlineKeyboardBuilder()
    ratios = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"]
    for r in ratios: 
        builder.button(text=r, callback_data=f"set_ratio_{r}")
    builder.button(text="🔙 Назад", callback_data="pf_back")
    builder.adjust(3, 2, 2, 1)
    return builder.as_markup()

def get_cancel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_wizard")
    return builder.as_markup()

def get_result_kb(db_message_id: int, is_pro: bool, cost: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔄 Ещё раз ({cost}🍌)", callback_data=f"reroll_{db_message_id}")
    builder.button(text=f"🎨 Изменить ({cost}🍌)", callback_data=f"edit_{db_message_id}")
    if is_pro:
        builder.button(text="📂 Скачать без сжатия", callback_data=f"download_{db_message_id}")
    builder.adjust(2, 1) if is_pro else builder.adjust(2)
    return builder.as_markup()

def get_categories_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🖼 Заменить объект", callback_data="cat_replace")
    builder.button(text="✨ AI-Фотосессия", callback_data="cat_photo")
    builder.button(text="🎭 В Аниме", callback_data="cat_anime")
    builder.button(text="🚗 Разбить тачку", callback_data="cat_crash")
    builder.button(text="🏚 Бомж в квартире", callback_data="cat_homeless")
    builder.button(text="🔥 Пожар", callback_data="cat_fire")
    builder.button(text="🎨 Свободный режим", callback_data="cat_free")
    builder.adjust(1, 2, 2, 2)
    return builder.as_markup()

# =====================================================================
# 🛫 ПРЕДПОЛЕТНЫЙ ЧЕК
# =====================================================================
async def start_preflight_check(message: types.Message, state: FSMContext, prompt: str, image_urls=None):
    user_id = message.from_user.id
    
    async with async_session() as session:
        pref_model = await get_user_model_preference(session, user_id)
    
    # ✅ Нормализуем URL
    normalized_urls = normalize_image_urls(image_urls)
    
    await state.update_data(
        pf_prompt=prompt, 
        pf_image_urls=normalized_urls,  # ✅ Всегда список
        pf_model=pref_model, 
        pf_ratio="1:1", 
        pf_quality="2k"
    )
    await state.set_state(GenState.preflight_check)
    
    cost = config.COST_PRO if pref_model == "pro" else config.COST_STANDARD
    text = (
        f"🎨 **Параметры генерации**\n\n"
        f"📝 **Запрос:** {prompt[:100]}...\n"
        f"💰 **Стоимость:** {cost} банан(а)\n\n"
        f"Настрой параметры и жми кнопку запуска 👇"
    )
    await message.answer(text, reply_markup=get_preflight_kb(pref_model, "1:1", "hd"), parse_mode="Markdown")

@router.callback_query(GenState.preflight_check, F.data == "pf_toggle_model")
async def cb_pf_toggle_model(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_model = data.get("pf_model", "standard")
    new_model = "pro" if current_model == "standard" else "standard"
    
    await state.update_data(pf_model=new_model)
    
    async with async_session() as session: 
        await set_user_model_preference(session, callback.from_user.id, new_model)
    
    ratio = data.get("pf_ratio", "1:1")
    quality = data.get("pf_quality", "hd")
    cost = config.COST_PRO if new_model == "pro" else config.COST_STANDARD
    
    text = (
        f"🎨 **Параметры генерации**\n\n"
        f"📝 **Запрос:** {data.get('pf_prompt', '')[:100]}...\n"
        f"💰 **Стоимость:** {cost} банан(а)\n\n"
        f"Настрой параметры и жми кнопку запуска 👇"
    )
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_preflight_kb(new_model, ratio, quality), 
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(GenState.preflight_check, F.data == "pf_toggle_quality")
async def cb_pf_toggle_quality(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_q = data.get("pf_quality", "2k")
    
    # ЦИКЛ: HD -> 2K -> 4K -> HD
    if current_q == "hd":
        new_q = "2k"
    elif current_q == "2k":
        new_q = "4k"
    else:
        new_q = "hd"
        
    await state.update_data(pf_quality=new_q)
    
    model = data.get("pf_model", "standard")
    ratio = data.get("pf_ratio", "1:1")
    
    await callback.message.edit_reply_markup(reply_markup=get_preflight_kb(model, ratio, new_q))
    await callback.answer()

@router.callback_query(GenState.preflight_check, F.data == "pf_select_ratio")
async def cb_pf_select_ratio(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(GenState.selecting_ratio)
    await callback.message.edit_text(
        "📐 **Выберите формат изображения:**", 
        reply_markup=get_ratio_kb(), 
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(GenState.selecting_ratio, F.data == "pf_back")
async def cb_pf_ratio_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(GenState.preflight_check)
    data = await state.get_data()
    cost = config.COST_PRO if data.get("pf_model") == "pro" else config.COST_STANDARD
    
    text = (
        f"🎨 **Параметры генерации**\n\n"
        f"📝 **Запрос:** {data.get('pf_prompt', '')[:100]}...\n"
        f"💰 **Стоимость:** {cost} банан(а)\n\n"
        f"Настрой параметры и жми кнопку запуска 👇"
    )
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_preflight_kb(
            data.get("pf_model"), 
            data.get("pf_ratio"), 
            data.get("pf_quality")
        ), 
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(GenState.selecting_ratio, F.data.startswith("set_ratio_"))
async def cb_pf_set_ratio(callback: types.CallbackQuery, state: FSMContext):
    new_ratio = callback.data.split("_")[2]
    await state.update_data(pf_ratio=new_ratio)
    await cb_pf_ratio_back(callback, state)

# 👇 ЗАМЕНИ ФУНКЦИЮ cb_pf_start НА ЭТУ 👇

@router.callback_query(GenState.preflight_check, F.data == "pf_start")
async def cb_pf_start(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    # 1. Считываем АКТУАЛЬНЫЕ данные из состояния (меню)
    prompt = data.get("pf_prompt")
    image_urls = data.get("pf_image_urls")
    model_type = data.get("pf_model")
    ratio = data.get("pf_ratio")
    quality = data.get("pf_quality")
    
    cost = config.COST_PRO if model_type == "pro" else config.COST_STANDARD
    use_pro = (model_type == "pro")
    
    # Логика разрешения
    resolution = "1K"
    if use_pro:
        if quality == "4k": resolution = "4K"
        elif quality == "2k": resolution = "2K"
    
    # 2. Просто уведомляем пользователя (Toast), НЕ трогая сообщение с меню
    await callback.answer(f"🚀 Запускаю...", show_alert=False)
    
    # 3. Запускаем генерацию
    # Меню останется висеть в чате, и юзер сможет поменять настройки и нажать снова
    await process_generation(
        callback.message, 
        callback.from_user.id, 
        prompt, 
        image_urls, 
        aspect_ratio=ratio, 
        cost=cost, 
        use_pro_model=use_pro, 
        resolution=resolution
    )
    
    # ⚠️ ВАЖНО: Мы НЕ делаем await state.clear()
    # Состояние остается активным, чтобы кнопки в меню продолжали работать

# =====================================================================
# ВХОДНЫЕ ТОЧКИ
# =====================================================================
@router.message(F.chat.type == "private", F.media_group_id, StateFilter(GenState.free_mode, None, GenState.preflight_check, GenState.selecting_ratio))
async def handle_album_input(message: types.Message, state: FSMContext, bot: Bot, album: list[types.Message] = None):
    await state.clear() # <--- ДОБАВИТЬ ЭТУ СТРОКУ, ЧТОБЫ ЗАБЫТЬ СТАРОЕ МЕНЮ
    """Обработка альбомов (2-10 фото)"""
    messages = album if album else [message]
    count = len(messages)
    
    if count > 4:
        await message.answer("✋ **Ого, слишком много!**\nМаксимум 4 фото.", parse_mode="Markdown")
        return
    
    image_urls = []
    full_caption = ""
    
    for msg in messages:
        if msg.photo:
            url = await get_photo_url(bot, msg.photo[-1].file_id)
            if url:  # ✅ Проверка
                image_urls.append(url)
        if msg.caption and not full_caption: 
            full_caption = msg.caption
    
    if not image_urls:
        await message.answer("❌ Не удалось получить фото.")
        return
    
    if count == 1:
        if full_caption:
            await start_preflight_check(message, state, full_caption, image_urls)
        else:
            await state.update_data(pending_image_urls=image_urls)
            await state.set_state(GenState.waiting_for_caption)
            await message.reply(
                "📸 **Готово! Фото поймал.**\nНапиши, что с ним сделать?", 
                parse_mode="Markdown"
            )
    else:  # >= 2 фото
        await state.update_data(pending_image_urls=image_urls)
        if full_caption:
            await start_preflight_check(message, state, full_caption, image_urls)
        else:
            await state.set_state(GenState.waiting_for_caption)
            await message.answer(
                f"✅ **Получено {count} фото!**\nТеперь напиши задачу (например: «Смешай их»).", 
                parse_mode="Markdown"
            )


@router.message(F.text == "✨ Начать творить")
async def cmd_start_creating(message: types.Message, state: FSMContext):
    # Явно ставим состояние "свободный режим"
    await state.set_state(GenState.free_mode)
    
    text = (
        "*Я готов творить!*\n"
        "Напиши, что создать, или пришли *от 1 до 4 фото*, которые нужно изменить или объединить 👇"
    )
    await message.answer(text, parse_mode="Markdown")

    # 👇 ВСТАВИТЬ ЭТОТ БЛОК ПЕРЕД handle_free_text 👇

@router.message(StateFilter(GenState.preflight_check, GenState.selecting_ratio), F.text)
async def handle_new_prompt_during_settings(message: types.Message, state: FSMContext):
    """
    Если юзер был в меню настроек (или выбора формата), 
    но решил просто написать новый промпт — начинаем всё заново.
    """
    # 1. Проверяем, не нажал ли он кнопку меню (Старт, Профиль и т.д.)
    if message.text in IGNORED_TEXTS: 
        return

    # 2. Сбрасываем старые данные (предыдущий промпт и настройки)
    await state.clear()
    
    # 3. Запускаем новую проверку с новым текстом
    await start_preflight_check(message, state, message.text, None)

# 👆 КОНЕЦ ВСТАВКИ 👆

# Дальше идет твоя старая функция:
# @router.message(F.text, StateFilter(GenState.free_mode, None))
# async def handle_free_text(...):

# 👇 ВСТАВИТЬ ЭТО ПОСЛЕ handle_new_prompt_during_settings 👇

@router.message(StateFilter(GenState.preflight_check, GenState.selecting_ratio), F.photo)
async def handle_new_photo_during_settings(message: types.Message, state: FSMContext, bot: Bot):
    """
    Если юзер был в меню настроек, но прислал ФОТО — сбрасываем и начинаем заново.
    """
    # 1. Если это альбом (несколько фото) — пропускаем, пусть обрабатывает handle_album_input
    # Но для этого нужно добавить состояние в handle_album_input или сбросить его тут.
    # Самый простой способ для альбома — просто сбросить состояние:
    if message.media_group_id:
        await state.clear()
        # Дальше aiogram сам передаст это в handle_album_input, так как состояние уже None
        # Но чтобы сработало наверняка, вызовем его вручную или просто вернемся (т.к. фильтр None сработает)
        return

    # 2. Сбрасываем старые настройки
    await state.clear()
    
    # 3. Обрабатываем фото (копируем логику из handle_general_photo)
    url = await get_photo_url(bot, message.photo[-1].file_id)
    
    if message.caption:
        # Если есть подпись — сразу в настройки
        await start_preflight_check(message, state, message.caption, [url])
    else:
        # Если подписи нет — просим ввести
        await state.update_data(pending_image_urls=[url])
        await state.set_state(GenState.waiting_for_caption)
        await message.reply("📸 **Фото принято!** Напиши, что с ним сделать.", parse_mode="Markdown")

# 👆 КОНЕЦ ВСТАВКИ 👆

@router.message(F.chat.type == "private", F.text, StateFilter(GenState.free_mode, None))
async def handle_free_text(message: types.Message, state: FSMContext):
    """Обработка текста без фото"""
    if message.text in IGNORED_TEXTS: 
        return
    await start_preflight_check(message, state, message.text, None)

@router.message(F.chat.type == "private", F.photo, StateFilter(GenState.free_mode, None))
async def handle_general_photo(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка одиночного фото"""
    if message.media_group_id: 
        return  # Обработается в handle_album_input
    print(f"🔥🔥🔥 МОЙ FILE ID: {message.photo[-1].file_id}")
    url = await get_photo_url(bot, message.photo[-1].file_id)
    
    if not url:
        await message.answer("❌ Не удалось получить фото.")
        return
    
    if message.caption:
        await start_preflight_check(message, state, message.caption, [url])
    else:
        await state.update_data(pending_image_urls=[url])
        await state.set_state(GenState.waiting_for_caption)
        await message.reply(
            "📸 **Фото принято!** Напиши, что с ним сделать.", 
            parse_mode="Markdown"
        )

@router.message(GenState.waiting_for_caption, F.text)
async def handle_delayed_caption(message: types.Message, state: FSMContext):
    """Обработка отложенного текста после фото"""
    user_prompt = message.text
    data = await state.get_data()
    image_urls = data.get("pending_image_urls")
    
    if not image_urls:
        await message.answer("❌ Ошибка: фото не найдены.")
        await state.clear()
        return
    
    await start_preflight_check(message, state, user_prompt, image_urls)

# =====================================================================
# ОБРАБОТКА РЕЗУЛЬТАТОВ
# =====================================================================
@router.callback_query(F.data.startswith("reroll_"))
async def cb_reroll(callback: types.CallbackQuery, bot: Bot):
    """Перегенерация с теми же параметрами"""
    await callback.answer("🔄 Запускаю...", show_alert=False)
    
    try:
        db_id = int(callback.data.split("_")[1])
        
        async with async_session() as session:
            history_item = await get_history_message_by_id(session, db_id)
        
        if not history_item or not history_item.content:
            await callback.message.answer("⚠️ Данные генерации устарели.")
            return
        
        params = json.loads(history_item.content)
        
        await callback.message.reply("🔄 **Ещё раз!**\nГенерирую...", parse_mode="Markdown")
        
        await process_generation(
            callback.message, 
            callback.from_user.id, 
            params.get("prompt"), 
            params.get("image_urls"),  # ✅ Уже список
            params.get("ratio", "1:1"), 
            params.get("cost", 1), 
            params.get("pro", False), 
            params.get("resolution", "1K")
        )
    except Exception as e:
        print(f"❌ Ошибка reroll: {e}")
        await callback.answer("❌ Ошибка перегенерации", show_alert=True)

@router.callback_query(F.data.startswith("download_"))
async def cb_download(callback: types.CallbackQuery, bot: Bot):
    await callback.answer("📥 Скачиваю оригинал...")
    
    try:
        db_id = int(callback.data.split("_")[1])
        async with async_session() as session: 
            history_item = await get_history_message_by_id(session, db_id)
        
        if not history_item:
            await callback.answer("❌ Запись не найдена.", show_alert=True)
            return

        if history_item.image_url:
            try:
                # 🛡️ ДОБАВИЛИ ТАЙМАУТ: Если качает дольше 30 сек — обрываем, чтобы не вешать сервер
                timeout = aiohttp.ClientTimeout(total=30)
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    # ssl=False оставляем, это необходимость для этого провайдера
                    async with session.get(history_item.image_url, ssl=False) as resp:
                        if resp.status == 200:
                            # Читаем файл
                            data = await resp.read()
                            
                            # Проверка на пустой файл
                            if len(data) == 0:
                                raise Exception("Пустой файл")

                            input_file = types.BufferedInputFile(data, filename=f"image_{db_id}.png")
                            
                            await bot.send_document(
                                chat_id=callback.from_user.id, 
                                document=input_file, 
                                caption="💎 Исходное качество (Original)"
                            )
                        else:
                            await callback.answer(f"Ошибка сервера IMG: {resp.status}", show_alert=True)
            except Exception as e:
                print(f"Ошибка скачивания: {e}")
                # Если не вышло скачать (таймаут или ошибка), пробуем отправить ссылку как текст/файл
                try:
                    await bot.send_message(
                        chat_id=callback.from_user.id,
                        text=f"💎 Не удалось загрузить файл напрямую. Вот ссылка на оригинал:\n{history_item.image_url}"
                    )
                except:
                    await callback.answer("❌ Не удалось получить файл.", show_alert=True)

        elif history_item.file_id:
            await bot.send_photo(
                chat_id=callback.from_user.id, 
                photo=history_item.file_id, 
                caption="📸 Копия из Telegram (Оригинал недоступен)"
            )
        else: 
            await callback.answer("❌ Файл потерян.", show_alert=True)

    except Exception as e:
        print(f"❌ Ошибка download: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)

@router.callback_query(F.data.startswith("edit_"))
async def cb_edit_result(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Редактирование существующего результата"""
    await callback.answer()
    
    try:
        db_id = int(callback.data.split("_")[1])
        
        async with async_session() as session: 
            history_item = await get_history_message_by_id(session, db_id)
        
        if not history_item or not history_item.file_id:
            await callback.answer("❌ Исходник не найден.", show_alert=True)
            return
        
        # Определяем стоимость из истории
        try: 
            params = json.loads(history_item.content)
            use_pro = params.get("pro", False)
        except: 
            use_pro = False
        
        cost = config.COST_PRO if use_pro else config.COST_STANDARD
        
        await state.update_data(
            editing_file_id=history_item.file_id,
            edit_use_pro=use_pro,
            edit_cost=cost
        )
        await state.set_state(GenState.waiting_for_edit_instruction)
        
        await callback.message.reply(
            f"🎨 **Режим редактирования** ({cost}🍌)\nЧто изменить?", 
            reply_markup=get_cancel_kb(), 
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"❌ Ошибка edit: {e}")
        await callback.answer("❌ Ошибка редактирования", show_alert=True)

@router.message(GenState.waiting_for_edit_instruction, F.text)
async def handle_edit_instruction(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка инструкции для редактирования"""
    instruction = message.text
    data = await state.get_data()
    file_id = data.get("editing_file_id")
    
    if not file_id:
        await message.answer("❌ Исходное фото не найдено.")
        await state.clear()
        return
    
    img_url = await get_photo_url(bot, file_id)
    
    if not img_url:
        await message.answer("❌ Не удалось получить фото.")
        await state.clear()
        return
    
    await message.answer("🎨 Принято! Открываю настройки...")
    await start_preflight_check(message, state, instruction, [img_url])

# =====================================================================
# КОМАНДЫ
# =====================================================================
@router.message(Command("clear"))
async def cmd_clear_history(message: types.Message, state: FSMContext):
    """Очистка истории"""
    async with async_session() as session: 
        await clear_history(session, message.from_user.id)
    await state.clear()
    await message.answer("🧹 **Память очищена!**", parse_mode="Markdown")


@router.callback_query(F.data == "cancel_wizard")
async def cb_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена мастера"""
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def cb_select_category(callback: types.CallbackQuery, state: FSMContext):
    """Выбор категории генерации"""
    await callback.answer()
    
    category = callback.data.split("_")[1]
    await state.clear()
    await state.update_data(selected_category=category)
    
    if category == "pro":
        await state.set_state(GenState.free_mode)
        await callback.message.edit_text(
            "🌟 **Режим Nano Banana PRO**\n\n"
            "💎 **Цена:** 3 банана\n"
            "🚀 **Качество:** Ultra HD.\n\n"
            "✍️ Отправь запрос.", 
            parse_mode="Markdown"
        )
        return
    
    if category == "replace":
        await state.set_state(GenState.waiting_for_base_image)
        await callback.message.edit_text(
            "🖼 **Режим замены (Шаг 1/3)**\nПришли **фото-основу**.", 
            reply_markup=get_cancel_kb(), 
            parse_mode="Markdown"
        )
        return
    
    if category == "free":
        await state.set_state(GenState.free_mode)
        await callback.message.edit_text(
            "🎨 **Свободный режим**\n\nПиши текст или присылай фото.", 
            parse_mode="Markdown"
        )
    else:
        await state.set_state(GenState.waiting_for_category_input)
        await callback.message.edit_text(
            "✅ Выбран режим. Пришли фото или текст.", 
            parse_mode="Markdown"
        )

# =====================================================================
# МАСТЕР ЗАМЕНЫ ОБЪЕКТА
# =====================================================================
@router.message(GenState.waiting_for_base_image, F.photo)
async def wizard_step_1(message: types.Message, state: FSMContext):
    """Шаг 1: Базовое фото"""
    await state.update_data(base_image_id=message.photo[-1].file_id)
    await state.set_state(GenState.waiting_for_ref_image)
    await message.reply(
        "👍 Основа есть! **Шаг 2/3:** Пришли **фото-донор**.", 
        reply_markup=get_cancel_kb(), 
        parse_mode="Markdown"
    )

@router.message(GenState.waiting_for_ref_image, F.photo)
async def wizard_step_2(message: types.Message, state: FSMContext):
    """Шаг 2: Фото-донор"""
    await state.update_data(ref_image_id=message.photo[-1].file_id)
    await state.set_state(GenState.waiting_for_replace_object_text)
    await message.reply(
        "👍 Донор есть! **Шаг 3/3:** Напиши **объект**.", 
        reply_markup=get_cancel_kb(), 
        parse_mode="Markdown"
    )

@router.message(GenState.waiting_for_replace_object_text, F.text)
async def wizard_step_3(message: types.Message, state: FSMContext, bot: Bot):
    """Шаг 3: Описание объекта"""
    data = await state.get_data()
    
    base_id = data.get("base_image_id")
    ref_id = data.get("ref_image_id")
    
    # ✅ ПРОВЕРКА
    if not base_id or not ref_id:
        await message.answer("❌ Ошибка: потеряны фото из предыдущих шагов.")
        await state.clear()
        return
    
    base_url = await get_photo_url(bot, base_id)
    ref_url = await get_photo_url(bot, ref_id)
    
    if not base_url or not ref_url:
        await message.answer("❌ Не удалось получить фото.")
        await state.clear()
        return
    
    final_prompt = (
        f"Replace the {message.text} in the first image with content from the second. "
        f"Seamless blending, maintain natural lighting and perspective."
    )
    
    await start_preflight_check(message, state, final_prompt, [base_url, ref_url])

@router.message(GenState.waiting_for_category_input)
async def handle_category_input(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка ввода в выбранной категории"""
    data = await state.get_data()
    category = data.get("selected_category", "free")
    
    photo_id = message.photo[-1].file_id if message.photo else data.get("stored_photo_id")
    user_text = message.text or message.caption or ""
    
    if not photo_id and not user_text:
        await message.answer("❌ Пришли фото или текст.")
        return
    
    image_url = await get_photo_url(bot, photo_id) if photo_id else None
    
    # ✅ ИСПРАВЛЕНО: передаём список или None
    image_urls_list = [image_url] if image_url else None
    
    await start_preflight_check(message, state, user_text, image_urls_list)

# ==============================================================================
# 🔥 ГЛАВНАЯ ФУНКЦИЯ ГЕНЕРАЦИИ
# ==============================================================================
async def process_generation(
    message: types.Message, 
    user_id: int, 
    prompt: str, 
    image_urls,  # list или None
    aspect_ratio: str = "1:1", 
    cost: int = 1, 
    use_pro_model: bool = False, 
    resolution: str = "1K"
):
    """Основная функция генерации изображений"""
    bot = message.bot 
    
    # 1. Проверка и списание баланса
    async with async_session() as session:
        has_balance = await check_and_deduct_balance(session, user_id, amount=cost)
        balance_left = await get_user_balance(session, user_id)

    if not has_balance:
        await message.answer(
            "🙈 <b>Ой, бананы закончились!</b>\n\n"
            "Ты так увлекся творчеством, что запасы иссякли.\n"
            "👇 Пополни запас прямо сейчас:",
            reply_markup=get_no_balance_kb(),
            parse_mode="HTML"
        )
        return

    # ✅ Нормализация URL
    final_urls = normalize_image_urls(image_urls)
    
    # 🔥 ОПРЕДЕЛЯЕМ СЦЕНАРИЙ: Простой vs Сложный
    is_complex_standard = (not use_pro_model and len(final_urls) >= 2)
    
# 2. Сообщение о старте (РАЗНОЕ для простого/сложного)
    if is_complex_standard:
        # 📌 СЦЕНАРИЙ Б: Сложный (Standard + много фото) - С ПРЕДУПРЕЖДЕНИЕМ
        wait_msg = await message.answer(
            "⏳ <b>Создаю...</b>\n\n"
            "⚠️ <b>Вы объединяете несколько фото в модели STANDARD.</b>\n"
            "Детали и сходство (особенно лица) могут искажаться.\n"
            "💡 <i>Для максимальной точности рекомендуем модель PRO.</i>",
            parse_mode="HTML"
        )
        should_delete_wait_msg = False  # НЕ УДАЛЯЕМ
    else:
        # 📌 СЦЕНАРИЙ А: Простой - ТОЛЬКО статус
        wait_msg = await message.answer("⏳ <b>Создаю...</b>", parse_mode="HTML")
        should_delete_wait_msg = True  # УДАЛЯЕМ

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
        
        # 4. Генерация
        result_data = await generate_image(
            bot, prompt, final_urls, False, 
            aspect_ratio, use_pro_model, None, resolution
        )
        
        # 5. Обработка результата
        result_file = None
        source_url = None
        
        if result_data and isinstance(result_data, tuple):
            result_file, source_url = result_data
        elif result_data: 
            result_file = result_data
        
        if result_file:
            # 🔥 УДАЛЯЕМ СООБЩЕНИЕ ТОЛЬКО ДЛЯ ПРОСТОГО СЦЕНАРИЯ
            if should_delete_wait_msg:
                try: 
                    await wait_msg.delete()
                except: 
                    pass
            
            # 6. Формирование caption
            safe_prompt = html.quote(prompt[:50])
            caption = (
                f"🍌 <b>Готово!</b>\n"
                f"💬 <i>«{safe_prompt}...»</i>\n"
                f"🔋 Осталось: <b>{balance_left}</b> 🍌\n\n"
                f"Сгенерировано в @nan0banana_bot"
            )
            
            # 7. Сжатие для превью
            file_bytes = result_file.data
            compressed_bytes = smart_compress_image(file_bytes)
            preview_file = types.BufferedInputFile(compressed_bytes, filename="result.png")
            
            # 8. Отправка
            try:
                sent_msg = await message.answer_photo(
                    preview_file, 
                    caption=caption, 
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"⚠️ Ошибка отправки фото: {e}")
                sent_msg = await message.answer_document(
                    result_file, 
                    caption=caption, 
                    parse_mode="HTML"
                )

            # 9. Сохранение в БД
            sent_file_id = (
                sent_msg.photo[-1].file_id if sent_msg.photo 
                else sent_msg.document.file_id
            )

            # 👇👇👇 🟢 1. ЛОГГЕР: УСПЕШНАЯ ГЕНЕРАЦИЯ 👇👇👇
            await log_generation(
                bot, 
                message.from_user, 
                prompt=prompt, 
                model="PRO" if use_pro_model else "Standard", 
                photo_file_id=sent_file_id
            )
            # 👆👆👆 -------------------------------------
            
            meta_data = json.dumps({
                "prompt": prompt,
                "image_urls": final_urls,
                "ratio": aspect_ratio,
                "cost": cost,
                "pro": use_pro_model,
                "resolution": resolution
            })
            
            async with async_session() as session:
                await add_history(
                    session, user_id, "user", prompt, 
                    has_image=bool(final_urls)
                )
                model_msg = await add_history(
                    session, user_id, "model", meta_data, 
                    has_image=True, 
                    file_id=sent_file_id, 
                    image_url=source_url
                )
                db_id = model_msg.id
            
            # 10. Добавление кнопок
            if db_id:
                await sent_msg.edit_reply_markup(
                    reply_markup=get_result_kb(db_id, use_pro_model, cost)
                )
        else:
            # ❌ NULL ОТВЕТ - ВОЗВРАТ ДЕНЕГ
            print("❌ API вернул NULL")

            # 👇👇👇 🔴 2. ЛОГГЕР: ОШИБКА API 👇👇👇
            await log_error(
                bot, 
                message.from_user.id, 
                message.from_user.username, 
                prompt, 
                error_text="API returned NULL (Blocked?)"
            )
            # 👆👆👆 ------------------------------

            async with async_session() as session: 
                await admin_change_balance(session, user_id, cost)
            
            try: 
                await wait_msg.edit_text(
                    "❌ <b>Ошибка генерации</b>\n\n"
                    "API не смог создать изображение.\n"
                    f"💰 {cost} 🍌 возвращены на баланс.",
                    parse_mode="HTML"
                )
            except: 
                await message.answer(
                    "❌ <b>Ошибка генерации</b>\n\n"
                    "API не смог создать изображение.\n"
                    f"💰 {cost} 🍌 возвращены на баланс.",
                    parse_mode="HTML"
                )
                
    except Exception as e:
        # ❌ КРИТИЧЕСКАЯ ОШИБКА - ВОЗВРАТ ДЕНЕГ
        print(f"❌ Критическая ошибка: {e}")

        # 👇👇👇 🔴 3. ЛОГГЕР: CRASH 👇👇👇
        await log_error(
            bot, 
            message.from_user.id, 
            message.from_user.username, 
            prompt, 
            error_text=f"CRASH: {str(e)[:50]}"
        )
        # 👆👆👆 --------------------------
        
        import traceback
        traceback.print_exc()
        
        async with async_session() as session: 
            await admin_change_balance(session, user_id, cost)
        
        try: 
            await wait_msg.edit_text(
                f"⚠️ <b>Техническая ошибка</b>\n\n"
                f"<code>{str(e)[:100]}</code>\n\n"
                f"💰 {cost} 🍌 возвращены на баланс.",
                parse_mode="HTML"
            )
        except: 
            await message.answer(
                f"⚠️ <b>Техническая ошибка</b>\n\n"
                f"<code>{str(e)[:100]}</code>\n\n"
                f"💰 {cost} 🍌 возвращены на баланс.",
                parse_mode="HTML"
            )