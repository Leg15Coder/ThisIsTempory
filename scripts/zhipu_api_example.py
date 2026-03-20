import requests
import json
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

zhipu_key = os.getenv('ZHIPU_API_KEY')

response = requests.post(
    url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
    headers={
        "Authorization": f"Bearer {zhipu_key}",
        "Content-Type": "application/json"
    },
    data=json.dumps({
        "model": "glm-4.7-flash",
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
    print(result)
    with open("zhipu_response.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    print("✅ УСПЕХ!")
else:
    print(f"❌ Ошибка: {response.text}")
