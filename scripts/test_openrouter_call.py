import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('OPENROUTER_API_KEY')
if not API_KEY:
    print('OPENROUTER_API_KEY not set in environment or .env')
    raise SystemExit(1)

url = 'https://openrouter.ai/api/v1/chat/completions'
headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

payload = {
    'model': os.getenv('OPENROUTER_MODEL', 'gpt-3.5-mini'),
    'messages': [{'role': 'user', 'content': 'Привет! Как дела?'}],
    'temperature': 0.2
}

print('POST', url)
print('Headers:', {k: ('<REDACTED>' if k.lower().find('auth')!=-1 else v) for k,v in headers.items()})
print('Payload sample:', {k: payload[k] for k in payload if k!='messages' or True})

try:
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    print('Status:', resp.status_code)
    print('Response headers:', dict(resp.headers))
    text = resp.text
    print('Response body (first 4000 chars):')
    print(text[:4000])
except Exception as e:
    print('Request failed:', repr(e))
    raise

