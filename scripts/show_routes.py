from app.main import app

routes = []
for r in app.routes:
    routes.append((getattr(r, 'path', None), getattr(r, 'name', None)))

print('ROUTES_COUNT:', len(routes))
for p, n in routes:
    print(p, '->', n)
