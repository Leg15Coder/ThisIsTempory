import requests

base = 'http://127.0.0.1:8000'

for path in ['/main', '/assistant/ui']:
    try:
        r = requests.get(base + path, timeout=5)
        print('\nGET', path, '->', r.status_code)
        text = r.text
        if path == '/main':
            print('Contains quickAssistantBtn:', ('quickAssistantBtn' in text))
            print('Contains assistantMainHub:', ('assistantMainHub' in text))
        if path == '/assistant/ui':
            print('Contains assistantRoot:', ('assistantRoot' in text))
            print('Contains assistantQuickSubmit:', ('assistantQuickSubmit' in text))
    except Exception as e:
        print('\nGET', path, 'failed:', e)

