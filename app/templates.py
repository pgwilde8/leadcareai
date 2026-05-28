"""Jinja2 template environment."""

from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["settings"] = get_settings()
