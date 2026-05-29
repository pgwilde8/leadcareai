"""Jinja2 template environment."""

from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.services.stripe_service import growth_checkout_configured

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["settings"] = get_settings()
templates.env.globals["is_checkout_available"] = growth_checkout_configured
