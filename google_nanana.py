import os
import asyncio
import base64
import time
from io import BytesIO
from dotenv import load_dotenv
from google import genai
from google.genai import types
import requests
from PIL import Image

load_dotenv()

# Настройка клиента
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def _download_image_as_pil(url: str) -> Image.Image:
    """Скачивает изображение по URL и возвращает PIL Image"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"❌ Ошибка загрузки изображения {url}: {e}")
        return None

def _run_sync_generation(prompt: str, image_urls: list = None):
    """
    Генерация изображений через Google Nano Banana
    """
    try:
        # Подготовка контента для запроса
        parts = []
        
        # Если есть изображения для редактирования - добавляем их
        if image_urls and len(image_urls) > 0:
            print(f"\n📷 Загружаю {len(image_urls)} изображений...")
            for idx, url in enumerate(image_urls, 1):
                img = _download_image_as_pil(url)
                if img:
                    parts.append(img)
                    print(f"  ✅ Изображение {idx} загружено")
                else:
                    print(f"  ⚠️ Изображение {idx} не загрузилось")
        
        # Добавляем промпт
        parts.append(prompt)
        
        # ЛОГИРОВАНИЕ
        print("\n" + "="*50)
        print(f"🚀 ОТПРАВКА В GOOGLE NANO BANANA")
        print("-" * 50)
        print(f"📝 Промпт: {prompt}")
        print(f"🖼️  Изображений: {len([p for p in parts if isinstance(p, Image.Image)])}")
        print("="*50 + "\n")
        
        # Конфигурация генерации
        generation_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            temperature=1.0,
        )
        
        # Генерация!
        print("⏳ Генерирую изображение...")
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=parts,
            config=generation_config
        )
        
        # Извлекаем изображение из ответа
        if response and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    print("✨ Изображение получено!")
                    
                    image_data = part.inline_data.data
                    
                    if isinstance(image_data, str):
                        image_bytes = base64.b64decode(image_data)
                    else:
                        image_bytes = image_data
                    
                    temp_filename = f"nanana_output_{int(time.time())}.png"
                    with open(temp_filename, "wb") as f:
                        f.write(image_bytes)
                    
                    print(f"💾 Сохранено: {temp_filename}")
                    
                    return temp_filename
                
                if hasattr(part, 'text') and part.text:
                    print(f"📄 Текст от модели: {part.text}")
        
        print("❌ Изображение не найдено в ответе")
        return None
        
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        import traceback
        traceback.print_exc()
        return None

async def generate_image(prompt: str, image_urls: list = None):
    """Асинхронная обертка"""
    return await asyncio.to_thread(_run_sync_generation, prompt, image_urls)


# ============================================
# ИНТЕРАКТИВНЫЙ РЕЖИМ
# ============================================
async def interactive_mode():
    """Интерактивный режим для тестирования через терминал"""
    print("\n" + "🍌"*25)
    print("    GOOGLE NANO BANANA - ИНТЕРАКТИВНЫЙ РЕЖИМ")
    print("🍌"*25 + "\n")
    
    while True:
        print("\n" + "-"*50)
        print("Выберите режим:")
        print("  1 - Генерация с нуля (text-to-image)")
        print("  2 - Редактирование изображения (image-to-image)")
        print("  q - Выход")
        print("-"*50)
        
        choice = input("\nВаш выбор: ").strip().lower()
        
        if choice == 'q':
            print("\n👋 До встречи!")
            break
        
        elif choice == '1':
            # Text-to-image
            print("\n🎨 РЕЖИМ: Генерация с нуля")
            prompt = input("Введите ваш промпт: ").strip()
            
            if not prompt:
                print("⚠️ Промпт не может быть пустым!")
                continue
            
            result = await generate_image(prompt=prompt)
            
            if result:
                print(f"\n🎉 Успех! Файл: {result}")
                
                # Спрашиваем, открыть ли файл
                open_file = input("Открыть изображение? (y/n): ").strip().lower()
                if open_file == 'y':
                    import platform
                    if platform.system() == 'Darwin':  # macOS
                        os.system(f'open "{result}"')
                    elif platform.system() == 'Windows':
                        os.system(f'start "{result}"')
                    else:  # Linux
                        os.system(f'xdg-open "{result}"')
            else:
                print("\n😞 Не удалось сгенерировать изображение")
        
        elif choice == '2':
            # Image-to-image
            print("\n✏️ РЕЖИМ: Редактирование изображения")
            
            # Собираем URL изображений
            image_urls = []
            print("\nВведите URL изображений (по одному, пустая строка для завершения):")
            
            idx = 1
            while True:
                url = input(f"  Изображение {idx}: ").strip()
                if not url:
                    break
                image_urls.append(url)
                idx += 1
            
            if not image_urls:
                print("⚠️ Нужно хотя бы одно изображение!")
                continue
            
            prompt = input("\nВведите промпт для редактирования: ").strip()
            
            if not prompt:
                print("⚠️ Промпт не может быть пустым!")
                continue
            
            result = await generate_image(prompt=prompt, image_urls=image_urls)
            
            if result:
                print(f"\n🎉 Успех! Файл: {result}")
                
                open_file = input("Открыть изображение? (y/n): ").strip().lower()
                if open_file == 'y':
                    import platform
                    if platform.system() == 'Darwin':  # macOS
                        os.system(f'open "{result}"')
                    elif platform.system() == 'Windows':
                        os.system(f'start "{result}"')
                    else:  # Linux
                        os.system(f'xdg-open "{result}"')
            else:
                print("\n😞 Не удалось сгенерировать изображение")
        
        else:
            print("⚠️ Неверный выбор! Попробуйте снова.")


# ============================================
# ТЕСТОВЫЙ РЕЖИМ (старый код)
# ============================================
async def test_mode():
    """Автоматические тесты"""
    print("🍌 GOOGLE NANO BANANA - ТЕСТОВЫЙ РЕЖИМ\n")
    
    async def test_text_to_image():
        print("🎨 ТЕСТ 1: Генерация изображения с нуля")
        result = await generate_image(
            prompt="A purple banana wearing sunglasses on a tropical beach at sunset"
        )
        print(f"✅ Результат: {result}\n")
    
    async def test_image_edit():
        print("✏️ ТЕСТ 2: Редактирование изображения")
        test_images = [
            "https://tempfileb.aiquickdraw.com/kieai/market/1763808680002_gCYb18g5.jpg",
            "https://tempfileb.aiquickdraw.com/kieai/market/1763808680046_ZfuerpbK.jpg"
        ]
        result = await generate_image(
            prompt="Replace the artwork in the frame with a portrait of the person shown in the reference photo. Keep the person hanging the picture and the room exactly the same.",
            image_urls=test_images
        )
        print(f"✅ Результат: {result}\n")
    
    await test_text_to_image()
    await test_image_edit()


if __name__ == "__main__":
    import sys
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Тестовый режим
        asyncio.run(test_mode())
    else:
        # Интерактивный режим (по умолчанию)
        asyncio.run(interactive_mode())