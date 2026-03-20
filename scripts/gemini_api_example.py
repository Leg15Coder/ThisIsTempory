import requests
import json
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

google_key = os.getenv('GEMINI_API_KEY')

if not google_key:
    print("❌ Укажите GEMINI_API_KEY в .env файле")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={google_key}"

response = requests.post(
    url=url,
    headers={"Content-Type": "application/json"},
    data=json.dumps({
        "contents": [{
            "parts": [{"text": "Привет! Как дела? Ответь одним предложением."}]
        }],
        "generationConfig": {
            "maxOutputTokens": 100
        }
    })
)

print(f"\n📊 Статус: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print("✅ УСПЕХ!")

    with open("gemini_response.json", "w", encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    answer = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    print(f"Ответ: {answer}")
else:
    print(f"❌ Ошибка: {response.text}")
