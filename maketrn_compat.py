from __future__ import annotations

import math
import time
from dataclasses import dataclass


METERS_PER_HG2_SAMPLE = 5
HG2_SAMPLES_PER_ZONE = 256
METERS_PER_ZONE = METERS_PER_HG2_SAMPLE * HG2_SAMPLES_PER_ZONE
MAKE_TRN_EMPTY_ELEVATION_MAX = 4094
MSVCR_CLOCKS_PER_SEC = 1000


@dataclass(frozen=True)
class StockGeometry:
    width_meters: int
    depth_meters: int
    zones_x: int
    zones_z: int


def normalize_make_trn_dimension(meters: int) -> int:
    """Reproduce MakeTRN's /w and /h integer normalization.

    The binary first truncates meters to 5 m samples, then rounds the sample
    count upward to a 256-sample boundary. This is subtly different from a
    straight ceil(meters / 1280) for values that are not multiples of 5.
    """
    meters = int(meters)
    if meters <= 0:
        raise ValueError("Terrain dimensions must be positive")
    samples = math.trunc(meters / METERS_PER_HG2_SAMPLE)
    samples = (samples + (HG2_SAMPLES_PER_ZONE - 1)) & ~(HG2_SAMPLES_PER_ZONE - 1)
    if samples <= 0:
        samples = HG2_SAMPLES_PER_ZONE
    return samples * METERS_PER_HG2_SAMPLE


def make_stock_geometry(width_meters: int, depth_meters: int) -> StockGeometry:
    width = normalize_make_trn_dimension(width_meters)
    depth = normalize_make_trn_dimension(depth_meters)
    return StockGeometry(
        width_meters=width,
        depth_meters=depth,
        zones_x=width // METERS_PER_ZONE,
        zones_z=depth // METERS_PER_ZONE,
    )


def validate_empty_elevation(value: int) -> int:
    """Validate the range actually accepted by MakeTRN 2.1.2's /e parser."""
    value = int(value)
    if not 0 <= value <= MAKE_TRN_EMPTY_ELEVATION_MAX:
        raise ValueError(
            f"Empty elevation must be 0..{MAKE_TRN_EMPTY_ELEVATION_MAX} "
            "for MakeTRN 2.1.2 compatibility"
        )
    return value


def make_trn_runtime_seed() -> int:
    """Approximate MSVCR120 clock() for legacy srand(clock()) behavior.

    Visual C++ clock() uses CLOCKS_PER_SEC=1000. Python process_time() is the
    closest cross-platform source because both measure process CPU time rather
    than wall-clock time. Only the low 32 bits matter to the emulated PRNG.
    """
    return int(time.process_time() * MSVCR_CLOCKS_PER_SEC) & 0xFFFFFFFF


def stock_trn_height(empty_elevation: int) -> float:
    """TRN Height written by MakeTRN's blank-create path."""
    return validate_empty_elevation(empty_elevation) * 0.1
