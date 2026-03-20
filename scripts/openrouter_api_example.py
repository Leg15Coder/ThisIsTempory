import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

openrouter_key = os.getenv('OPENROUTER_API_KEY')

if not openrouter_key:
    print("❌ Укажите OPENROUTER_API_KEY в .env файле")
    exit(1)

print(f"🔑 Использую ключ: {openrouter_key[:10]}...")

# Запрос к OpenRouter (попробуем hunter-alpha)
response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-OpenRouter-Title": "Free LLM Test"
    },
    data=json.dumps({
        "model": "openrouter/hunter-alpha",  # Новая бесплатная модель
        "messages": [
            {
                "role": "user",
                "content": "Привет! Как дела? Ответь одним предложением."
            }
        ],
        "max_tokens": 100
    })
)

print(f"\n📊 Статус: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print("✅ УСПЕХ!")
    print(f"Модель: {result.get('model', 'не указана')}")

    with open("openrouter_response.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"Ответ: {result['choices'][0]['message']['content']}")
else:
    print(f"❌ Ошибка: {response.text}")
