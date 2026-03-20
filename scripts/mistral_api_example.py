import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

mistral_key = os.getenv('MISTRAL_API_KEY')

if not mistral_key:
    print("❌ Укажите MISTRAL_API_KEY в .env файле")
    exit(1)

print(f"🔑 Использую ключ: {mistral_key[:10]}...")

response = requests.post(
    url="https://api.mistral.ai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {mistral_key}",
        "Content-Type": "application/json"
    },
    data=json.dumps({
        "model": "mistral-small-latest",  # Бесплатная модель
        "messages": [
            {
                "role": "user",
                "content": "Привет! Как дела? Ответь одним предложением."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 100
    })
)

print(f"\n📊 Статус: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print("✅ УСПЕХ!")

    with open("mistral_response.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"Ответ: {result['choices'][0]['message']['content']}")
else:
    print(f"❌ Ошибка: {response.text}")
