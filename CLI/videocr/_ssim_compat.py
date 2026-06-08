"""Drop-in replacement for the `fast_ssim` package on platforms where its
bundled native library (libssim.so) cannot be loaded (e.g. macOS / arm64).

Exposes a single `ssim(a, b, data_range=255)` function matching the call
signature used by VideOCR, returning a structural-similarity score in [0, 1].
Backed by scikit-image's well-tested implementation.
"""
from __future__ import annotations

import numpy as np
from skimage.metrics import structural_similarity as _sk_ssim


def ssim(a: np.ndarray, b: np.ndarray, data_range: float = 255) -> float:
    a = np.asarray(a)
    b = np.asarray(b)

    if a.shape != b.shape or a.size == 0:
        return 0.0

    # Pick an odd window size that fits the smallest spatial dimension.
    spatial = a.shape[:2]
    win = min(7, min(spatial))
    if win % 2 == 0:
        win -= 1

    # Too small for a meaningful window: fall back to a normalized closeness.
    if win < 3:
        diff = np.abs(a.astype(np.float64) - b.astype(np.float64))
        return float(1.0 - diff.mean() / data_range)

    kwargs = {"data_range": data_range, "win_size": win}
    if a.ndim == 3:
        kwargs["channel_axis"] = -1

    return float(_sk_ssim(a, b, **kwargs))
