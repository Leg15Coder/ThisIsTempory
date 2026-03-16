import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
import json
import logging
from app.services.gemini_service import GeminiService
from app.services.memory_service import MemoryService
from app.services.stt_service import STTService
from app.assistants.intent_router import IntentRouter
from app.assistants.fast_assistant import FastAssistant
from app.models.assistant_models import AssistantRequest

# instantiate services (GeminiService is configured to return local fallback in dev)
_g = GeminiService()
_ms = MemoryService()
_stt = STTService(_g)
_ir = IntentRouter(_g)
_fast = FastAssistant(_g, _ms, _stt, _ir)

async def main():
    logging.basicConfig(level=logging.DEBUG)
    print('TEST START')
    try:
        status = _g.get_status()
        print('LLM STATUS:', json.dumps(status, ensure_ascii=False, indent=2))
    except Exception as e:
        print('FAILED to get gemini status:', repr(e))
    try:
        req = AssistantRequest(text='Привет, расскажи анекдот', user_id='1')
        resp = await _fast.handle(req)
        print('RESPONSE:')
        print(json.dumps(resp.model_dump(), ensure_ascii=False, indent=2))
    except Exception as e:
        print('ERROR:', repr(e))

    print('TEST END')

asyncio.run(main())
