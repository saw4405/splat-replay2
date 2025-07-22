from typing import cast

from numpy.typing import NDArray
import numpy as np

Frame = NDArray[np.uint8]


def as_frame(array: np.ndarray) -> Frame:
    """np.ndarrayをFrame型として型キャストするユーティリティ関数。"""
    return cast(Frame, array)
