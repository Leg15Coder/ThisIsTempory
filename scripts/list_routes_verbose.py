from importlib import import_module

try:
    m = import_module('app.main')
    app = getattr(m, 'app')
except Exception as e:
    print('Error importing app.main:', e)
    raise

for r in app.routes:
    try:
        print('PATH:', getattr(r,'path',None),'NAME:', getattr(r,'name',None),'ENDPOINT:', getattr(r,'endpoint',None))
    except Exception as e:
        print('Error printing route', e)
