from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
from PIL import Image, ImageDraw

MAT_ZONE_SIZE = 64
MAT_ENTRY_BYTES = 2
WORLD_ZONE_METERS = 1280.0
PAINTER_MAX_ELEVATION_DM = 4095.0
PAINTER_MAX_MATERIAL = 7


@dataclass(frozen=True)
class MatEntry:
    base: int
    next: int
    cap: int
    flip: int
    rotation: int
    variant: int
    reserved: int = 0

    @property
    def mix(self) -> int:
        return ((self.cap & 1) << 3) | ((self.flip & 1) << 2) | (self.rotation & 3)


@dataclass
class PaintStats:
    total_tiles: int = 0
    solid_tiles: int = 0
    cap_tiles: int = 0
    diagonal_tiles: int = 0
    ambiguous_tiles: int = 0
    unsupported_transition_tiles: int = 0
    unmatched_samples: int = 0


@dataclass(frozen=True)
class TRNPainterConfig:
    layers: tuple[dict, ...]
    texture_types: tuple[int, ...]
    transitions: frozenset[tuple[int, int]]
    min_x: float = 0.0
    min_z: float = 0.0
    width: Optional[float] = None
    depth: Optional[float] = None


def _check_range(name: str, value: int, low: int, high: int) -> None:
    if not low <= int(value) <= high:
        raise ValueError(f"{name} must be in {low}..{high}, got {value}")


def encode_entry(
    base: int,
    next_mat: int,
    cap: int = 0,
    flip: int = 0,
    rotation: int = 0,
    variant: int = 0,
    reserved: int = 0,
) -> int:
    """Encode one MAT entry using the documented 16-bit little-endian bitfield.

    ``reserved`` exists only for lossless/tolerant decoding of legacy files.
    New files should leave it at zero. WorldBuilder intentionally generates
    only the documented four variants (0..3), even though BZMapIO historically
    treats the whole low nibble as a variant value.
    """
    _check_range("base", base, 0, 15)
    _check_range("next_mat", next_mat, 0, 15)
    _check_range("cap", cap, 0, 1)
    _check_range("flip", flip, 0, 1)
    _check_range("rotation", rotation, 0, 3)
    _check_range("variant", variant, 0, 3)
    _check_range("reserved", reserved, 0, 3)
    return (
        (int(variant) & 0x3)
        | ((int(reserved) & 0x3) << 2)
        | ((int(rotation) & 0x3) << 4)
        | ((int(flip) & 0x1) << 6)
        | ((int(cap) & 0x1) << 7)
        | ((int(next_mat) & 0xF) << 8)
        | ((int(base) & 0xF) << 12)
    )


def encode_mix_entry(base: int, next_mat: int, mix: int, variant: int = 0) -> int:
    _check_range("mix", mix, 0, 15)
    return encode_entry(
        base=base,
        next_mat=next_mat,
        cap=(mix >> 3) & 1,
        flip=(mix >> 2) & 1,
        rotation=mix & 3,
        variant=variant,
    )


def decode_entry(value: int) -> MatEntry:
    _check_range("MAT entry", value, 0, 0xFFFF)
    return MatEntry(
        base=(value >> 12) & 0xF,
        next=(value >> 8) & 0xF,
        cap=(value >> 7) & 0x1,
        flip=(value >> 6) & 0x1,
        rotation=(value >> 4) & 0x3,
        variant=value & 0x3,
        reserved=(value >> 2) & 0x3,
    )


def entry_to_bytes(value: int) -> bytes:
    _check_range("MAT entry", value, 0, 0xFFFF)
    return int(value).to_bytes(2, "little")


def entry_from_bytes(raw: bytes) -> int:
    if len(raw) != 2:
        raise ValueError("A MAT entry is exactly two bytes")
    return int.from_bytes(raw, "little")


def expected_mat_bytes(zones_x: int, zones_z: int) -> int:
    if zones_x <= 0 or zones_z <= 0:
        raise ValueError("MAT zone dimensions must be positive")
    return zones_x * zones_z * MAT_ZONE_SIZE * MAT_ZONE_SIZE * MAT_ENTRY_BYTES


def pack_mat_zones(entries: np.ndarray, zones_x: int, zones_z: int) -> bytes:
    """Pack a global MAT grid into Battlezone zone-major storage.

    The input array is indexed [z, x] with row 0 at the south edge. Zones are
    written southwest first, west-to-east within each zone row, then north.
    Each 64x64 zone is itself row-major south-to-north.
    """
    array = np.asarray(entries)
    expected_shape = (zones_z * MAT_ZONE_SIZE, zones_x * MAT_ZONE_SIZE)
    if array.shape != expected_shape:
        raise ValueError(f"MAT shape {array.shape} does not match {expected_shape}")
    if array.size and (np.min(array) < 0 or np.max(array) > 0xFFFF):
        raise ValueError("MAT entries must fit in uint16")

    encoded = np.rint(array).astype("<u2")
    output = bytearray(expected_mat_bytes(zones_x, zones_z))
    cursor = 0
    zone_bytes = MAT_ZONE_SIZE * MAT_ZONE_SIZE * MAT_ENTRY_BYTES
    for zone_z in range(zones_z):
        for zone_x in range(zones_x):
            z0 = zone_z * MAT_ZONE_SIZE
            x0 = zone_x * MAT_ZONE_SIZE
            zone = encoded[z0 : z0 + MAT_ZONE_SIZE, x0 : x0 + MAT_ZONE_SIZE]
            raw = zone.astype("<u2", copy=False).tobytes(order="C")
            output[cursor : cursor + zone_bytes] = raw
            cursor += zone_bytes
    return bytes(output)


def unpack_mat_zones(payload: bytes, zones_x: int, zones_z: int) -> np.ndarray:
    expected = expected_mat_bytes(zones_x, zones_z)
    if len(payload) != expected:
        raise ValueError(f"MAT size mismatch: expected {expected} bytes, found {len(payload)}")

    raw = np.frombuffer(payload, dtype="<u2")
    full = np.empty((zones_z * MAT_ZONE_SIZE, zones_x * MAT_ZONE_SIZE), dtype=np.uint16)
    cursor = 0
    zone_entries = MAT_ZONE_SIZE * MAT_ZONE_SIZE
    for zone_z in range(zones_z):
        for zone_x in range(zones_x):
            zone = raw[cursor : cursor + zone_entries].reshape((MAT_ZONE_SIZE, MAT_ZONE_SIZE))
            z0 = zone_z * MAT_ZONE_SIZE
            x0 = zone_x * MAT_ZONE_SIZE
            full[z0 : z0 + MAT_ZONE_SIZE, x0 : x0 + MAT_ZONE_SIZE] = zone
            cursor += zone_entries
    return full


def write_mat(path: os.PathLike | str, entries: np.ndarray, zones_x: int, zones_z: int) -> None:
    payload = pack_mat_zones(entries, zones_x, zones_z)
    with open(path, "wb") as stream:
        stream.write(payload)


def read_mat(path: os.PathLike | str, zones_x: int, zones_z: int) -> np.ndarray:
    with open(path, "rb") as stream:
        return unpack_mat_zones(stream.read(), zones_x, zones_z)


def calculate_slope_degrees(height_dm: np.ndarray, zones_x: int, zones_z: int) -> np.ndarray:
    """Return physical terrain slope in degrees from decimeter height samples."""
    height = np.asarray(height_dm, dtype=np.float32)
    if height.ndim != 2:
        raise ValueError("height data must be a 2-D array")
    if zones_x <= 0 or zones_z <= 0:
        raise ValueError("zone dimensions must be positive")
    if height.shape[1] % zones_x or height.shape[0] % zones_z:
        raise ValueError("height dimensions are not divisible by zone dimensions")

    zone_w = height.shape[1] // zones_x
    zone_h = height.shape[0] // zones_z
    if zone_w != zone_h:
        raise ValueError("Battlezone terrain zones must be square")
    sample_spacing_m = WORLD_ZONE_METERS / float(zone_w)
    height_m = height * 0.1
    grad_z, grad_x = np.gradient(height_m, sample_spacing_m, sample_spacing_m)
    return np.degrees(np.arctan(np.hypot(grad_x, grad_z)))


def _numeric(value: str) -> float:
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", value)
    if not match:
        raise ValueError(f"not a numeric value: {value!r}")
    return float(match.group(0))


def parse_trn_painter(path: os.PathLike | str) -> TRNPainterConfig:
    """Parse the TRN portions needed by the procedural MAT painter."""
    sections: dict[str, list[tuple[str, str]]] = {}
    current = ""
    with open(path, "r", encoding="cp1252", errors="replace") as stream:
        for original in stream:
            line = original.strip()
            if not line or line.startswith("//") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1].strip()
                sections.setdefault(current, [])
                continue
            if "=" in line and current:
                key, value = line.split("=", 1)
                sections.setdefault(current, []).append((key.strip(), value.strip()))

    size_values = {"minx": 0.0, "minz": 0.0, "width": None, "depth": None}
    texture_types: set[int] = set()
    transitions: set[tuple[int, int]] = set()
    layer_rows: list[tuple[int, dict]] = []

    for section, items in sections.items():
        lower = section.lower()
        values = {k.lower(): v for k, v in items}
        if lower == "size":
            for key in size_values:
                if key in values:
                    try:
                        size_values[key] = _numeric(values[key])
                    except ValueError:
                        pass
            continue

        tex_match = re.fullmatch(r"texturetype(\d+)", lower)
        if tex_match:
            base = int(tex_match.group(1))
            texture_types.add(base)
            for key, _ in items:
                trans_match = re.match(r"(?:capto|diagonalto)(\d+)_", key, re.IGNORECASE)
                if trans_match:
                    transitions.add((base, int(trans_match.group(1))))
            continue

        layer_match = re.fullmatch(r"layer(\d+)", lower)
        if layer_match:
            try:
                material = int(_numeric(values.get("material", "8")))
                if material >= 8:
                    continue
                layer_rows.append(
                    (
                        int(layer_match.group(1)),
                        {
                            "mat_id": material,
                            "min_h": _numeric(values.get("elevationstart", "0")),
                            "max_h": _numeric(values.get("elevationend", "4095")),
                            "min_s": _numeric(values.get("slopestart", "0")),
                            "max_s": _numeric(values.get("slopeend", "90")),
                            "mask_path": "",
                        },
                    )
                )
            except (ValueError, TypeError):
                continue

    layer_rows.sort(key=lambda item: item[0])
    return TRNPainterConfig(
        layers=tuple(row for _, row in layer_rows),
        texture_types=tuple(sorted(texture_types)),
        transitions=frozenset(transitions),
        min_x=float(size_values["minx"] or 0.0),
        min_z=float(size_values["minz"] or 0.0),
        width=size_values["width"],
        depth=size_values["depth"],
    )


def validate_paint_rules(rules: Iterable[dict]) -> list[str]:
    warnings: list[str] = []
    rules = list(rules)
    if not rules:
        return ["No paint rules are defined."]

    for i, rule in enumerate(rules):
        try:
            mat_id = int(rule["mat_id"])
            min_h, max_h = float(rule["min_h"]), float(rule["max_h"])
            min_s, max_s = float(rule["min_s"]), float(rule["max_s"])
        except (KeyError, TypeError, ValueError):
            warnings.append(f"Rule {i}: malformed numeric fields")
            continue
        if not 0 <= mat_id <= PAINTER_MAX_MATERIAL:
            warnings.append(f"Rule {i} (Mat{mat_id}): painter material must be 0..{PAINTER_MAX_MATERIAL}")
        if min_h > max_h:
            warnings.append(f"Rule {i} (Mat{mat_id}): Min Height > Max Height")
        if min_s > max_s:
            warnings.append(f"Rule {i} (Mat{mat_id}): Min Slope > Max Slope")
        if min_h < 0 or max_h > PAINTER_MAX_ELEVATION_DM:
            warnings.append(
                f"Rule {i} (Mat{mat_id}): elevation must be 0..{int(PAINTER_MAX_ELEVATION_DM)} decimeters"
            )
        if min_s < 0 or max_s > 90:
            warnings.append(f"Rule {i} (Mat{mat_id}): slope must be 0..90 degrees")
        mask_path = str(rule.get("mask_path", "") or "")
        if mask_path and not mask_path.upper().startswith("PATH:") and not os.path.exists(mask_path):
            warnings.append(f"Rule {i} (Mat{mat_id}): mask file does not exist: {mask_path}")
    return warnings


def _mode(values: np.ndarray) -> int:
    flat = np.asarray(values, dtype=np.int64).ravel()
    if flat.size == 0:
        return 0
    return int(np.bincount(flat, minlength=16).argmax())


def _rasterize_path_mask(
    h: int,
    w: int,
    bzn_paths: list[dict],
    label: str,
    min_x: float,
    min_z: float,
    world_width: float,
    world_depth: float,
) -> np.ndarray:
    target = next((p for p in bzn_paths if p.get("label") == label), None)
    if not target or not target.get("points") or world_width <= 0 or world_depth <= 0:
        return np.zeros((h, w), dtype=bool)
    image = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(image)
    points = []
    for x, z in target["points"]:
        px = ((float(x) - min_x) / world_width) * w
        pz = ((float(z) - min_z) / world_depth) * h
        points.append((px, pz))
    if target.get("type") == 3 and len(points) >= 3:
        draw.polygon(points, fill=255)
    elif len(points) >= 2:
        draw.line(points, fill=255, width=max(1, round(min(h, w) / 128)))
    return np.asarray(image) > 127


def classify_samples(
    height_dm: np.ndarray,
    rules: Iterable[dict],
    zones_x: int,
    zones_z: int,
    bzn_paths: Optional[list[dict]] = None,
    min_x: float = 0.0,
    min_z: float = 0.0,
    world_width: Optional[float] = None,
    world_depth: Optional[float] = None,
) -> tuple[np.ndarray, int]:
    height = np.asarray(height_dm, dtype=np.float32)
    slope = calculate_slope_degrees(height, zones_x, zones_z)
    materials = np.zeros(height.shape, dtype=np.uint8)
    matched = np.zeros(height.shape, dtype=bool)
    bzn_paths = bzn_paths or []
    world_width = float(world_width or zones_x * WORLD_ZONE_METERS)
    world_depth = float(world_depth or zones_z * WORLD_ZONE_METERS)

    for rule in rules:
        mat_id = int(rule["mat_id"])
        mask = (
            (height >= float(rule["min_h"]))
            & (height <= float(rule["max_h"]))
            & (slope >= float(rule["min_s"]))
            & (slope <= float(rule["max_s"]))
        )
        mask_path = str(rule.get("mask_path", "") or "")
        if mask_path:
            if mask_path.upper().startswith("PATH:"):
                path_label = mask_path.split(":", 1)[1]
                mask &= _rasterize_path_mask(
                    height.shape[0],
                    height.shape[1],
                    bzn_paths,
                    path_label,
                    min_x,
                    min_z,
                    world_width,
                    world_depth,
                )
            elif os.path.exists(mask_path):
                mask_img = Image.open(mask_path).convert("L")
                if mask_img.size != (height.shape[1], height.shape[0]):
                    mask_img = mask_img.resize(
                        (height.shape[1], height.shape[0]), Image.Resampling.NEAREST
                    )
                mask &= np.asarray(mask_img) > 127
        materials[mask] = mat_id
        matched |= mask
    return materials, int(np.size(matched) - np.count_nonzero(matched))


_CAP_MIX_BY_SIDE = {
    "east": 6,
    "west": 4,
    "north": 5,
    "south": 7,
}
_DIAG_MIX_BY_CORNER = {
    "sw": 13,
    "nw": 14,
    "ne": 15,
    "se": 12,
}


def _transition_mix(corners: tuple[int, int, int, int], next_mat: int) -> Optional[int]:
    """Return Mix for corners ordered (SW, SE, NE, NW), or None if ambiguous."""
    flags = tuple(value == next_mat for value in corners)
    count = sum(flags)
    if count == 1:
        return _DIAG_MIX_BY_CORNER[("sw", "se", "ne", "nw")[flags.index(True)]]
    if count == 2:
        sw, se, ne, nw = flags
        if se and ne:
            return _CAP_MIX_BY_SIDE["east"]
        if sw and nw:
            return _CAP_MIX_BY_SIDE["west"]
        if ne and nw:
            return _CAP_MIX_BY_SIDE["north"]
        if sw and se:
            return _CAP_MIX_BY_SIDE["south"]
    return None


def encode_transition_from_corners(
    corners: tuple[int, int, int, int],
    transitions: Optional[set[tuple[int, int]] | frozenset[tuple[int, int]]] = None,
    default_material: int = 0,
) -> tuple[int, str]:
    """Encode one MAT tile from quadrant materials ordered SW, SE, NE, NW."""
    unique = sorted(set(int(v) for v in corners))
    if len(unique) == 1:
        material = unique[0]
        return encode_mix_entry(material, material, 0), "solid"
    if len(unique) != 2:
        return encode_mix_entry(default_material, default_material, 0), "ambiguous"

    a, b = unique
    candidates: list[tuple[int, int]] = []
    if transitions:
        if (a, b) in transitions:
            candidates.append((a, b))
        if (b, a) in transitions:
            candidates.append((b, a))
        if not candidates:
            return encode_mix_entry(default_material, default_material, 0), "unsupported"
    else:
        candidates.append((a, b))
        candidates.append((b, a))

    for base, next_mat in candidates:
        mix = _transition_mix(corners, next_mat)
        if mix is not None:
            kind = "diagonal" if mix >= 8 else "cap"
            return encode_mix_entry(base, next_mat, mix), kind

    if transitions and any(sum(v == next_mat for v in corners) == 3 for _, next_mat in candidates):
        return encode_mix_entry(default_material, default_material, 0), "unsupported"

    return encode_mix_entry(default_material, default_material, 0), "ambiguous"


def generate_mat(
    height_dm: np.ndarray,
    rules: Iterable[dict],
    zones_x: int,
    zones_z: int,
    transitions: Optional[set[tuple[int, int]] | frozenset[tuple[int, int]]] = None,
    bzn_paths: Optional[list[dict]] = None,
    min_x: float = 0.0,
    min_z: float = 0.0,
    world_width: Optional[float] = None,
    world_depth: Optional[float] = None,
    default_material: int = 0,
) -> tuple[np.ndarray, PaintStats]:
    warnings = validate_paint_rules(rules)
    if warnings:
        raise ValueError("; ".join(warnings))

    height = np.asarray(height_dm, dtype=np.float32)
    if height.ndim != 2:
        raise ValueError("height data must be two-dimensional")
    if height.shape[1] % zones_x or height.shape[0] % zones_z:
        raise ValueError("height dimensions are not divisible by zone dimensions")
    zone_w = height.shape[1] // zones_x
    zone_h = height.shape[0] // zones_z
    if zone_w != zone_h:
        raise ValueError("height zones must be square")
    if zone_w % MAT_ZONE_SIZE:
        raise ValueError(
            f"height zone size {zone_w} is not divisible by MAT zone size {MAT_ZONE_SIZE}"
        )
    scale = zone_w // MAT_ZONE_SIZE
    if scale < 2 or scale % 2:
        raise ValueError(
            "height data needs at least 2x2 samples per MAT entry quadrant "
            "(Redux depth-7/depth-8 terrain is supported)"
        )

    sample_mats, unmatched = classify_samples(
        height,
        rules,
        zones_x,
        zones_z,
        bzn_paths=bzn_paths,
        min_x=min_x,
        min_z=min_z,
        world_width=world_width,
        world_depth=world_depth,
    )
    out = np.empty((zones_z * MAT_ZONE_SIZE, zones_x * MAT_ZONE_SIZE), dtype=np.uint16)
    stats = PaintStats(total_tiles=out.size, unmatched_samples=unmatched)
    half = scale // 2

    for mz in range(out.shape[0]):
        for mx in range(out.shape[1]):
            z0 = mz * scale
            x0 = mx * scale
            patch = sample_mats[z0 : z0 + scale, x0 : x0 + scale]
            corners = (
                _mode(patch[:half, :half]),
                _mode(patch[:half, half:]),
                _mode(patch[half:, half:]),
                _mode(patch[half:, :half]),
            )
            entry, kind = encode_transition_from_corners(
                corners,
                transitions=transitions,
                default_material=default_material,
            )
            out[mz, mx] = entry
            if kind == "solid":
                stats.solid_tiles += 1
            elif kind == "cap":
                stats.cap_tiles += 1
            elif kind == "diagonal":
                stats.diagonal_tiles += 1
            elif kind == "unsupported":
                stats.unsupported_transition_tiles += 1
            else:
                stats.ambiguous_tiles += 1
    return out, stats
