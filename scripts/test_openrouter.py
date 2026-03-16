import sys
from pathlib import Path
# Add project root to sys.path so 'app' package can be imported
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json, traceback
from app.services.openrouter_service import OpenRouterService

s = OpenRouterService()
print('STATUS:', json.dumps(s.get_status(), ensure_ascii=False, indent=2))
try:
    resp = s.generate_content([{'role':'user','content':'Hello from local test'}])
    print('RESPONSE OK:')
    print(json.dumps(resp, ensure_ascii=False, indent=2))
except Exception as e:
    print('GENERATE ERROR:', repr(e))
    try:
        if hasattr(e, 'response') and e.response is not None:
            print('HTTP STATUS:', getattr(e.response, 'status_code', None))
            print('BODY:', e.response.text)
    except Exception:
        traceback.print_exc()
