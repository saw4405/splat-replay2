from typing import cast

import numpy as np
from numpy.typing import NDArray

Frame = NDArray[np.uint8]


def as_frame(array: np.ndarray) -> Frame:
    """np.ndarrayをFrame型として型キャストするユーティリティ関数。"""
    return cast(Frame, array)
