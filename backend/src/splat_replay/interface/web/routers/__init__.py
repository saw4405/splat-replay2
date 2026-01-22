"""Web APIルーター群。"""

from .assets import create_assets_router
from .events import create_events_router
from .metadata import create_metadata_router
from .notifications import create_notifications_router
from .process import create_process_router
from .recording import create_recording_router
from .settings import create_settings_router
from .setup import create_setup_router

__all__ = [
    "create_assets_router",
    "create_events_router",
    "create_metadata_router",
    "create_notifications_router",
    "create_recording_router",
    "create_settings_router",
    "create_setup_router",
    "create_process_router",
]
