"""画像読み込みのためのユーティリティ関数。"""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def imread_unicode(
    file_path: Path, flags: int = cv2.IMREAD_COLOR
) -> Optional[np.ndarray]:
    """
    日本語を含むパスでも画像を読み込めるようにする関数。

    cv2.imread() は日本語パスを扱えないため、numpy 経由で読み込む。

    Args:
        file_path: 読み込む画像ファイルのパス
        flags: OpenCV の imread フラグ (IMREAD_COLOR, IMREAD_GRAYSCALE など)

    Returns:
        読み込んだ画像の ndarray。失敗時は None。
    """
    try:
        # バイナリとしてファイルを読み込み
        img_buffer = np.fromfile(str(file_path), dtype=np.uint8)
        if img_buffer.size == 0:
            return None

        # バッファから画像をデコード
        img = cv2.imdecode(img_buffer, flags)
        return img
    except Exception:
        return None
