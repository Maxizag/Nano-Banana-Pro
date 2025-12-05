import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Загрузка переменных окружения
# Ищем файл .env на уровень выше папки app
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

# --- БОТ И ДОСТУПЫ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
KIE_API_KEY = os.getenv("KIE_API_KEY")

# Список ID администраторов (числа)
# Замени на свой ID!
ADMIN_IDS = [
    627352144, 
    # 123456789, # Можно добавить второго админа
]

# --- ЭКОНОМИКА (Цены) ---
START_BALANCE = 3        # Сколько даем новому юзеру
COST_STANDARD = 1        # Цена обычной генерации
COST_PRO = 4             # Цена PRO режима
BONUS_AMOUNT = 5         # Бонус за подписку

# --- ССЫЛКИ И ТЕКСТЫ ---
CHANNEL_USERNAME = "@YourChannel" # Твой канал (для проверки подписки)
CHANNEL_LINK = "https://t.me/YourChannel"
SUPPORT_USERNAME = "@tvoj_username"

# --- НАСТРОЙКИ НЕЙРОСЕТЕЙ ---
# Google (Free Core)
GOOGLE_MODEL_NAME = "gemini-2.5-flash-image"

# Kie.ai (Premium Core)
KIE_URL = "https://api.kie.ai/api/v1/jobs"
KIE_MODEL_EDIT = "google/nano-banana-edit"
KIE_MODEL_GEN = "google/nano-banana"
KIE_MODEL_PRO = "nano-banana-pro"