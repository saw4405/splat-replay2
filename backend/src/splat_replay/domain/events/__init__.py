"""Domain events package.

Type-safe domain events for event-driven architecture.
All domain events should inherit from DomainEvent base class.
"""

from .asset_events import (
    AssetEditedDeleted,
    AssetEditedSaved,
    AssetRecordedDeleted,
    AssetRecordedMetadataUpdated,
    AssetRecordedSaved,
    AssetRecordedSubtitleUpdated,
)
from .base import DomainEvent
from .battle_events import (
    BattleFinished,
    BattleInterrupted,
    BattleMatchingStarted,
    BattleResultDetected,
    BattleStarted,
    ScheduleChanged,
)
from .process_events import (
    AutoProcessPending,
    AutoProcessStarted,
    AutoSleepPending,
    AutoSleepStarted,
    EditUploadCompleted,
)
from .recording_events import (
    PowerOffDetected,
    RecordingCancelled,
    RecordingMetadataUpdated,
    RecordingPaused,
    RecordingResumed,
    RecordingStarted,
    RecordingStopped,
)
from .speech_events import SpeechRecognized, SpeechRecognizerListening

__all__ = [
    # Base
    "DomainEvent",
    # Recording events
    "RecordingStarted",
    "RecordingPaused",
    "RecordingResumed",
    "RecordingStopped",
    "RecordingCancelled",
    "RecordingMetadataUpdated",
    "PowerOffDetected",
    # Asset events
    "AssetRecordedSaved",
    "AssetRecordedDeleted",
    "AssetRecordedMetadataUpdated",
    "AssetRecordedSubtitleUpdated",
    "AssetEditedSaved",
    "AssetEditedDeleted",
    # Battle events
    "BattleMatchingStarted",
    "BattleStarted",
    "BattleInterrupted",
    "BattleFinished",
    "BattleResultDetected",
    "ScheduleChanged",
    # Process events
    "EditUploadCompleted",
    "AutoProcessPending",
    "AutoProcessStarted",
    "AutoSleepPending",
    "AutoSleepStarted",
    # Speech events
    "SpeechRecognizerListening",
    "SpeechRecognized",
]
