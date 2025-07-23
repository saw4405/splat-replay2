"""OCR ユーティリティ。"""

from __future__ import annotations


from typing import Optional, Literal

import numpy as np
import pytesseract

from splat_replay.domain.services import OCRPort

# ps_modeの型を定義する
PS_MODE = Literal[
    "AUTO",
    "SINGLE_COLUMN",
    "SINGLE_LINE",
    "SINGLE_WORD",
    "SINGLE_BLOCK",
    "SINGLE_CHAR",
]


class TesseractOCR(OCRPort):
    """OCRユーティリティクラス。"""

    PSM_MAPPING = {
        "AUTO": 3,
        "SINGLE_COLUMN": 4,
        "SINGLE_BLOCK": 6,
        "SINGLE_LINE": 7,
        "SINGLE_WORD": 8,
        "SINGLE_CHAR": 10,
    }

    def recognize_text(
        self,
        image: np.ndarray,
        ps_mode: Optional[str] = None,
        whitelist: Optional[str] = None,
    ) -> str | None:
        try:
            config = ""
            if ps_mode:
                psm_value = self.PSM_MAPPING.get(ps_mode.upper())
                if psm_value is not None:
                    config += f"--psm {psm_value} "
            if whitelist:
                config += f"-c tessedit_char_whitelist={whitelist}"
            text = str(pytesseract.image_to_string(image, config=config))
            return text
        except pytesseract.TesseractNotFoundError:
            return None
        except Exception:
            return None
