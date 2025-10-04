"""Application-level event type constants.

Clean Architecture: Exposed for interface/infrastructure and GUI layers.
No infrastructure dependencies.
"""

from __future__ import annotations

__all__ = ["EventTypes"]


class EventTypes:
    # Recorder
    RECORDER_RESET = "recorder.reset"
    RECORDER_STATE = "recorder.state"
    RECORDER_OPERATION = "recorder.operation"
    POWER_OFF_DETECTED = "power.off.detected"
    RECORDER_MATCH = "recorder.match"
    RECORDER_METADATA_UPDATED = "recorder.metadata.updated"
    # Editor
    EDITOR_STARTED = "editor.started"
    EDITOR_PROGRESS = "editor.progress"
    EDITOR_FINISHED = "editor.finished"
    # Uploader
    UPLOADER_STARTED = "uploader.started"
    UPLOADER_PROGRESS = "uploader.progress"
    UPLOADER_ITEM_FINISHED = "uploader.item.finished"
    UPLOADER_FINISHED = "uploader.finished"
    # Progress generic
    PROGRESS_PREFIX = "progress."
    # Video Asset Repository (recorded assets)
    ASSET_RECORDED_SAVED = "asset.recorded.saved"
    ASSET_RECORDED_METADATA_UPDATED = "asset.recorded.metadata.updated"
    ASSET_RECORDED_SUBTITLE_UPDATED = "asset.recorded.subtitle.updated"
    ASSET_RECORDED_DELETED = "asset.recorded.deleted"
    # Edited assets
    ASSET_EDITED_SAVED = "asset.edited.saved"
    ASSET_EDITED_DELETED = "asset.edited.deleted"
