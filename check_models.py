import os
from dotenv import load_dotenv
from google import genai

# Загрузка API ключа
load_dotenv()
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_KEY:
    print("❌ Нет GOOGLE_API_KEY в .env")
    exit(1)

# Создаём клиент
client = genai.Client(api_key=GOOGLE_KEY)

print("\n" + "="*70)
print("🔍 ПРОВЕРКА ДОСТУПНЫХ МОДЕЛЕЙ GEMINI")
print("="*70 + "\n")

try:
    # Получаем все модели
    models = list(client.models.list())
    
    print(f"📊 Всего моделей доступно: {len(models)}\n")
    
    # Категории моделей
    image_models = []
    text_models = []
    other_models = []
    
    for model in models:
        model_name = model.name
        
        # Проверяем поддержку generateContent
        supports_generate = False
        if hasattr(model, 'supported_generation_methods'):
            supports_generate = 'generateContent' in model.supported_generation_methods
        
        # Категоризируем
        if 'image' in model_name.lower():
            image_models.append((model_name, supports_generate, model))
        elif 'flash' in model_name.lower() or 'pro' in model_name.lower():
            text_models.append((model_name, supports_generate, model))
        else:
            other_models.append((model_name, supports_generate, model))
    
    # МОДЕЛИ ДЛЯ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ
    print("🎨 МОДЕЛИ ДЛЯ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ:")
    print("-"*70)
    
    if image_models:
        for model_name, supports_generate, model in image_models:
            status = "✅" if supports_generate else "❌"
            print(f"\n{status} {model_name}")
            
            if hasattr(model, 'supported_generation_methods'):
                print(f"   📋 Методы: {', '.join(model.supported_generation_methods)}")
            
            if hasattr(model, 'input_token_limit'):
                print(f"   🔢 Токены: {model.input_token_limit}")
            
            if hasattr(model, 'description'):
                print(f"   📝 Описание: {model.description[:100]}...")
    else:
        print("⚠️ Модели для генерации изображений не найдены")
    
    # ТЕКСТОВЫЕ МОДЕЛИ (Gemini Flash/Pro)
    print("\n\n💬 ТЕКСТОВЫЕ МОДЕЛИ (GEMINI FLASH/PRO):")
    print("-"*70)
    
    if text_models:
        for model_name, supports_generate, model in text_models[:10]:  # Показываем первые 10
            status = "✅" if supports_generate else "❌"
            print(f"\n{status} {model_name}")
            
            if hasattr(model, 'supported_generation_methods'):
                methods = ', '.join(model.supported_generation_methods)
                print(f"   📋 Методы: {methods}")
    
    # ПОИСК КОНКРЕТНЫХ МОДЕЛЕЙ
    print("\n\n🔎 ПОИСК NANO BANANA:")
    print("-"*70)
    
    search_terms = [
        "gemini-2.5-flash-image",
        "gemini-2-5-flash-image", 
        "nano-banana",
        "flash-image",
        "image-generation"
    ]
    
    found_matches = []
    
    for model in models:
        model_name = model.name.lower()
        for term in search_terms:
            if term.lower() in model_name:
                found_matches.append(model)
                break
    
    if found_matches:
        print(f"✅ Найдено {len(found_matches)} похожих моделей:\n")
        for model in found_matches:
            supports = "✅" if hasattr(model, 'supported_generation_methods') and 'generateContent' in model.supported_generation_methods else "❌"
            print(f"{supports} {model.name}")
    else:
        print("❌ Модели с 'image' или 'flash-image' не найдены")
    
    # ПОЛНЫЙ СПИСОК ВСЕХ МОДЕЛЕЙ
    print("\n\n📋 ВСЕ ДОСТУПНЫЕ МОДЕЛИ (полный список):")
    print("-"*70)
    
    for idx, model in enumerate(models, 1):
        supports = "✅" if hasattr(model, 'supported_generation_methods') and 'generateContent' in model.supported_generation_methods else "❌"
        print(f"{idx:3}. {supports} {model.name}")
    
    # РЕКОМЕНДАЦИИ
    print("\n\n💡 РЕКОМЕНДАЦИИ ДЛЯ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ:")
    print("-"*70)
    
    recommended = []
    for model in models:
        name = model.name
        supports = hasattr(model, 'supported_generation_methods') and 'generateContent' in model.supported_generation_methods
        
        if supports and 'image' in name.lower():
            recommended.append(name)
    
    if recommended:
        print("Попробуй эти модели в следующем порядке:\n")
        for idx, model_name in enumerate(recommended, 1):
            print(f"  {idx}. MODEL_NAME = \"{model_name}\"")
    else:
        print("⚠️ Модели для генерации изображений не найдены.")
        print("\nВозможные причины:")
        print("  1. Регион не поддерживается")
        print("  2. Нужна оплата/биллинг")
        print("  3. API ключ из старого проекта")
        
        print("\n🔧 Решение:")
        print("  1. Создай новый API ключ: https://aistudio.google.com/apikey")
        print("  2. Убедись что регион поддерживается")
        print("  3. Включи биллинг (если нужно)")

except Exception as e:
    print(f"❌ Ошибка при получении списка моделей: {e}")
    import traceback
    traceback.print_exc()
    
    print("\n\n🔧 ВОЗМОЖНЫЕ ПРИЧИНЫ ОШИБКИ:")
    print("-"*70)
    print("1. Неверный API ключ")
    print("2. API ключ не активирован")
    print("3. Нет доступа к Gemini API")
    print("4. Проблемы с сетью")
    
    print("\n💡 ЧТО ДЕЛАТЬ:")
    print("-"*70)
    print("1. Проверь API ключ в .env")
    print("2. Создай новый ключ: https://aistudio.google.com/apikey")
    print("3. Убедись что интернет работает")

print("\n" + "="*70)
print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
print("="*70 + "\n")