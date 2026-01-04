"""タイムスケジュール（動画編集の時間帯区分）モデル。"""

import datetime
from typing import List, Tuple

# 1日を2時間ごとに区切るタイムレンジ
TIME_RANGES: List[Tuple[datetime.time, datetime.time]] = [
    (datetime.time(1, 0), datetime.time(3, 0)),
    (datetime.time(3, 0), datetime.time(5, 0)),
    (datetime.time(5, 0), datetime.time(7, 0)),
    (datetime.time(7, 0), datetime.time(9, 0)),
    (datetime.time(9, 0), datetime.time(11, 0)),
    (datetime.time(11, 0), datetime.time(13, 0)),
    (datetime.time(13, 0), datetime.time(15, 0)),
    (datetime.time(15, 0), datetime.time(17, 0)),
    (datetime.time(17, 0), datetime.time(19, 0)),
    (datetime.time(19, 0), datetime.time(21, 0)),
    (datetime.time(21, 0), datetime.time(23, 0)),
    (datetime.time(23, 0), datetime.time(1, 0)),
]
