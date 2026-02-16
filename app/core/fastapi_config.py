from fastapi.templating import Jinja2Templates
from app.core.config import get_settings

settings = get_settings()

templates = Jinja2Templates(directory=settings.templates_path)
