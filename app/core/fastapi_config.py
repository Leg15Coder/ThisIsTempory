from fastapi.templating import Jinja2Templates
from app.core.config import get_settings

settings = get_settings()

templates = Jinja2Templates(directory=settings.templates_path)

_orig_template_response = templates.TemplateResponse

def template_response(name: str, context: dict, status_code: int = None, headers: dict = None, media_type: str = None):
    ctx = dict(context or {})
    req = ctx.get('request')
    if req:
        if 'current_user' not in ctx:
            if 'user' in ctx:
                ctx['current_user'] = ctx.get('user')
            else:
                ctx['current_user'] = getattr(req.state, 'current_user', None)

    effective_status = status_code if status_code is not None else 200
    return _orig_template_response(name, ctx, status_code=effective_status, headers=headers, media_type=media_type)


templates.TemplateResponse = template_response
