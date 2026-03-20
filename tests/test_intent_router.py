import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from app.assistants.intent_router import IntentRouter

class DummyLLM:
    async def generate_text(self, prompt, response_mime_type=None):
        return {"text": '{"intent": "create_quest", "confidence": 0.9, "parameters": {"title":"Test"}, "missing_parameters": []}', "json": None}

async def run_test():
    llm = DummyLLM()
    router = IntentRouter(llm)
    res = await router.detect_intent("Создай квест тест")
    print(res)

if __name__ == '__main__':
    asyncio.run(run_test())
