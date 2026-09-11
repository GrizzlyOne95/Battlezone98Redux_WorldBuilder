from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

import numpy as np


METERS_PER_HG2_SAMPLE = 5
HG2_SAMPLES_PER_ZONE = 256
HGT_SAMPLES_PER_ZONE = 128
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
    Values below 5 m quantize to zero samples in MakeTRN; WorldBuilder rejects
    them instead of attempting to create a zero-sized terrain.
    """
    meters = int(meters)
    if meters <= 0:
        raise ValueError("Terrain dimensions must be positive")
    samples = math.trunc(meters / METERS_PER_HG2_SAMPLE)
    samples = (samples + (HG2_SAMPLES_PER_ZONE - 1)) & ~(HG2_SAMPLES_PER_ZONE - 1)
    if samples <= 0:
        raise ValueError("Terrain dimensions must be at least 5 meters")
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


def unpack_hgt_zones(payload: bytes, zones_x: int, zones_z: int) -> np.ndarray:
    """Decode MakeTRN's legacy HGT payload into a north-unmodified raster.

    HGT has no header. It stores 128x128 unsigned-16 blocks in zone-major
    order. MakeTRN masks every source sample with 0x0fff before interpolation.
    """
    zones_x = int(zones_x)
    zones_z = int(zones_z)
    if zones_x <= 0 or zones_z <= 0:
        raise ValueError("HGT zone dimensions must be positive")
    zone_samples = HGT_SAMPLES_PER_ZONE * HGT_SAMPLES_PER_ZONE
    expected = zones_x * zones_z * zone_samples * 2
    if len(payload) != expected:
        raise ValueError(f"HGT size mismatch: expected {expected} bytes, found {len(payload)}")

    raw = np.frombuffer(payload, dtype="<u2") & 0x0FFF
    out = np.empty(
        (zones_z * HGT_SAMPLES_PER_ZONE, zones_x * HGT_SAMPLES_PER_ZONE),
        dtype=np.uint16,
    )
    cursor = 0
    for zone_z in range(zones_z):
        for zone_x in range(zones_x):
            zone = raw[cursor : cursor + zone_samples].reshape(
                (HGT_SAMPLES_PER_ZONE, HGT_SAMPLES_PER_ZONE)
            )
            z0 = zone_z * HGT_SAMPLES_PER_ZONE
            x0 = zone_x * HGT_SAMPLES_PER_ZONE
            out[z0 : z0 + HGT_SAMPLES_PER_ZONE, x0 : x0 + HGT_SAMPLES_PER_ZONE] = zone
            cursor += zone_samples
    return out


def upsample_hgt_to_hg2(legacy: np.ndarray) -> np.ndarray:
    """Reproduce MakeTRN's 128->256 samples/zone HGT interpolation.

    The disassembled interpolator splits every source quad along A->C and
    evaluates the Redux grid at half-sample coordinates. At those exact 0.5
    positions the piecewise-triangle formula reduces to the four assignments
    below. At the far right/bottom edges MakeTRN clamps the next index by
    reusing the current source sample.
    """
    src = np.asarray(legacy, dtype=np.uint16) & 0x0FFF
    if src.ndim != 2 or src.shape[0] == 0 or src.shape[1] == 0:
        raise ValueError("HGT raster must be a non-empty 2D array")

    src32 = src.astype(np.uint32)
    right = np.empty_like(src32)
    right[:, :-1] = src32[:, 1:]
    right[:, -1] = src32[:, -1]
    down = np.empty_like(src32)
    down[:-1, :] = src32[1:, :]
    down[-1, :] = src32[-1, :]
    diagonal = np.empty_like(src32)
    diagonal[:-1, :-1] = src32[1:, 1:]
    diagonal[-1, :-1] = src32[-1, 1:]
    diagonal[:-1, -1] = src32[1:, -1]
    diagonal[-1, -1] = src32[-1, -1]

    out = np.empty((src.shape[0] * 2, src.shape[1] * 2), dtype=np.uint16)
    out[0::2, 0::2] = src
    out[0::2, 1::2] = ((src32 + right) // 2).astype(np.uint16)
    out[1::2, 0::2] = ((src32 + down) // 2).astype(np.uint16)
    out[1::2, 1::2] = ((src32 + diagonal) // 2).astype(np.uint16)
    return out


def read_hgt_as_hg2(path: os.PathLike | str, zones_x: int, zones_z: int) -> np.ndarray:
    with open(path, "rb") as stream:
        legacy = unpack_hgt_zones(stream.read(), zones_x, zones_z)
    return upsample_hgt_to_hg2(legacy)
