import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
import json
import sqlite3
import traceback
from app.core.config import get_settings
from app.services.gemini_service import GeminiService
from app.services.memory_service import MemoryService
from app.assistants.fast_assistant import FastAssistant
from app.services.stt_service import STTService
from app.assistants.intent_router import IntentRouter
from app.models.assistant_models import AssistantRequest

print('DIAGNOSE START')
try:
    s = get_settings()
    print('Settings:')
    print(json.dumps({
        'assistant_force_local_llm': bool(s.assistant_force_local_llm),
        'gemini_api_key': bool(s.gemini_api_key),
        'openai_api_key': bool(s.openai_api_key),
        'perplexity_api_key': bool(s.perplexity_api_key),
        'openrouter_api_key': bool(s.openrouter_api_key),
        'gemini_base_url': s.gemini_base_url,
        'openrouter_base_url': s.openrouter_base_url,
    }, ensure_ascii=False, indent=2))
except Exception as e:
    print('Failed to load settings:', repr(e))

# show cache rows
try:
    conn = sqlite3.connect('assistant_memory.db')
    cur = conn.cursor()
    rows = cur.execute("SELECT cache_key, substr(payload,1,200) as p FROM assistant_cache").fetchall()
    print('assistant_cache rows:', len(rows))
    for k,p in rows[:10]:
        print(' -', k, p)
    conn.close()
except Exception as e:
    print('Failed to read assistant_cache:', repr(e))

# instantiate services
try:
    g = GeminiService()
    ms = MemoryService()
    stt = STTService(g)
    ir = IntentRouter(g)
    fa = FastAssistant(g, ms, stt, ir)
    print('Services instantiated')
except Exception as e:
    print('Failed to instantiate services:', repr(e))
    traceback.print_exc()

# print gemini status
try:
    status = g.get_status()
    print('Gemini status:')
    print(json.dumps(status, ensure_ascii=False, indent=2))
except Exception as e:
    print('Failed to get Gemini status:', repr(e))
    traceback.print_exc()

# try one assistant call
try:
    print('Calling FastAssistant.handle...')
    req = AssistantRequest(text='Тестовый запрос, скажи привет', user_id='1')
    resp = asyncio.run(fa.handle(req))
    print('Response:')
    print(json.dumps(resp.model_dump(), ensure_ascii=False, indent=2))
except Exception as e:
    print('Assistant call failed:', repr(e))
    traceback.print_exc()

print('DIAGNOSE END')

