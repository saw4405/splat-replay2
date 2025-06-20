from __future__ import annotations

from datetime import datetime
from pathlib import Path

from splat_replay.domain.models.match import Match
from splat_replay.domain.models.rule import Rule
from splat_replay.domain.models.stage import Stage
from splat_replay.domain.models.result import Result
from splat_replay.domain.models.video_clip import VideoClip


def test_match_dataclass() -> None:
    start = datetime.now()
    match = Match(rule=Rule.TURF_WAR, stage=Stage.SCORCH_GORGE, start_at=start)
    assert match.rule is Rule.TURF_WAR
    assert match.stage is Stage.SCORCH_GORGE
    assert match.start_at == start
    assert match.result is None
    assert match.end_at is None
    assert match.kill is None
    assert match.death is None
    assert match.special is None
    assert match.rate is None
    assert isinstance(match.id, str)


def test_video_clip() -> None:
    clip = VideoClip(path=Path("foo.mp4"), match_id="abc")
    assert clip.path.name == "foo.mp4"
    assert clip.match_id == "abc"
