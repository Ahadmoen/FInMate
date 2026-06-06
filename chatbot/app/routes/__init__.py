# Old routes module — kept so existing imports don't break.
# main.py now uses app.api.* directly.
from app.api import chat, ingest  # noqa: F401
