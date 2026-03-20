import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

groq_key = os.getenv('GROQ_API_KEY')

if not groq_key:
    print("❌ Укажите GROQ_API_KEY в .env файле")
    exit(1)

print(f"🔑 Использую ключ: {groq_key[:10]}...")

response = requests.post(
    url="https://api.groq.com/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    },
    data=json.dumps({
        "model": "llama-3.3-70b-versatile",  # Бесплатная модель
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

    with open("groq_response.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"Ответ: {result['choices'][0]['message']['content']}")
else:
    print(f"❌ Ошибка: {response.text}")
