"""Fixed technical-quality settings, independent of the pipeline's weights."""

from dataclasses import dataclass
from math import isclose, isfinite


@dataclass(frozen=True)
class QualityConfig:
    max_sharpness_edge: int = 512
    laplacian_kernel: int = 1
    alpha_background: int = 127
    dark_threshold: int = 12
    bright_threshold: int = 243
    sharpness_reference: float = 1000.0
    contrast_reference: float = 64.0
    normalization: str = "log_sharpness"
    weights: tuple[float, float, float] = (0.45, 0.35, 0.20)

    def __post_init__(self) -> None:
        integer_fields = (
            self.max_sharpness_edge, self.laplacian_kernel, self.alpha_background,
            self.dark_threshold, self.bright_threshold,
        )
        if any(type(value) is not int for value in integer_fields):
            raise ValueError("Image scale, kernel, background and thresholds must be integers")
        if self.max_sharpness_edge < 1 or self.laplacian_kernel not in (1, 3):
            raise ValueError("Expected a positive evaluation edge and a Laplacian kernel of 1 or 3")
        if not 0 <= self.alpha_background <= 255:
            raise ValueError("Alpha background must be between 0 and 255")
        if not 0 <= self.dark_threshold < self.bright_threshold <= 255:
            raise ValueError("Exposure thresholds must be ordered and between 0 and 255")
        if any(not isfinite(ref) or ref <= 0 for ref in
               (self.sharpness_reference, self.contrast_reference)):
            raise ValueError("Normalization references must be positive and finite")
        if self.normalization not in ("log_sharpness", "linear"):
            raise ValueError("Unknown quality normalization")
        weights = tuple(self.weights)
        if (len(weights) != 3 or any(not 0 <= weight <= 1 for weight in weights)
                or not isclose(sum(weights), 1.0, rel_tol=0, abs_tol=1e-9)):
            raise ValueError("Quality weights must be nonnegative and sum to 1")
        object.__setattr__(self, "weights", weights)


DEFAULT_QUALITY_CONFIG = QualityConfig()
