from typing import List
from pathlib import Path
import datetime

import srt

from splat_replay.shared.logger import get_logger
from splat_replay.application.interfaces import SubtitleEditorPort


logger = get_logger()


class SubtitleEditor(SubtitleEditorPort):
    def merge(self, subtitles: List[Path], video_length: List[float]) -> str:
        if len(subtitles) != len(video_length):
            raise ValueError("字幕ファイルと動画の長さのリストの長さが一致しません。")

        logger.info("字幕を結合します")
        combined_subtitles: List[srt.Subtitle] = []
        offset = datetime.timedelta(seconds=0)
        for subtitle_path, length in zip(subtitles, video_length):
            if subtitle_path.exists():
                srt_str = subtitle_path.read_text(encoding="utf-8")
                sts = list(srt.parse(srt_str))
                for st in sts:
                    st.start += offset
                    st.end += offset
                combined_subtitles.extend(sts)

            offset += datetime.timedelta(seconds=length)

        return srt.compose(combined_subtitles)
