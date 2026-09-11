from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

import numpy as np

from hg2_codec import HG2Header

BZ_ZONE_WORLD_SIZE = 1280.0
_FIELD_RE_TEMPLATE = r"^\s*{name}(?:\s*\[\s*\d+\s*\])?\s*=\s*(.*)$"


def hg2_world_size(header: HG2Header) -> tuple[float, float]:
    """Return the Battlezone world width/depth represented by an HG2."""
    return (
        float(header.zones_x) * BZ_ZONE_WORLD_SIZE,
        float(header.zones_z) * BZ_ZONE_WORLD_SIZE,
    )


def hg2_north_up(heights: np.ndarray) -> np.ndarray:
    """Convert HG2's south-first row convention to a north-at-top display array."""
    array = np.asarray(heights)
    if array.ndim != 2:
        raise ValueError("HG2 height data must be a 2D array")
    return np.flipud(array)


def world_to_canvas(
    world_x: float,
    world_z: float,
    *,
    min_x: float,
    min_z: float,
    world_width: float,
    world_depth: float,
    draw_rect: tuple[float, float, float, float],
) -> tuple[float, float]:
    """Map Battlezone +X/+Z coordinates into a north-at-top canvas rectangle."""
    if world_width <= 0 or world_depth <= 0:
        raise ValueError("Mission world width/depth must be positive")

    left, top, pixel_width, pixel_height = draw_rect
    rel_x = (float(world_x) - float(min_x)) / float(world_width)
    rel_z = (float(world_z) - float(min_z)) / float(world_depth)

    return (
        float(left) + rel_x * float(pixel_width),
        float(top) + (1.0 - rel_z) * float(pixel_height),
    )


def _clean_bzn_value(value: str) -> str:
    return value.strip().strip('"').strip("'").rstrip("\x00").strip()


def _next_scalar(lines: list[str], start: int) -> str | None:
    for index in range(start, len(lines)):
        value = lines[index].strip()
        if not value:
            continue
        # A new structure marker/field before a scalar means the requested
        # field did not have a simple next-line value.
        if value.startswith("[") or re.match(r"^[A-Za-z_][^=]*=", value):
            return None
        return _clean_bzn_value(value)
    return None


def extract_ascii_bzn_field(path: os.PathLike | str, field_names: Iterable[str]) -> str | None:
    """Read a simple scalar field from an ASCII BZN without guessing line offsets."""
    raw = Path(path).read_bytes()
    if b"\x00" in raw:
        raise ValueError(
            "Binary BZN file detected. Mission Visualizer currently requires an ASCII BZN."
        )
    text = raw.decode("cp1252")
    lines = text.splitlines()

    for name in field_names:
        pattern = re.compile(_FIELD_RE_TEMPLATE.format(name=re.escape(name)), re.IGNORECASE)
        for index, line in enumerate(lines):
            match = pattern.match(line)
            if not match:
                continue
            inline = _clean_bzn_value(match.group(1))
            if inline:
                return inline
            value = _next_scalar(lines, index + 1)
            if value:
                return value
    return None


def extract_terrain_name(path: os.PathLike | str) -> str | None:
    return extract_ascii_bzn_field(path, ("TerrainName", "g_TerrainName"))


def _case_insensitive_child(directory: Path, name: str) -> Path | None:
    """Return the actual directory entry matching name, preserving on-disk casing."""
    if not directory.is_dir():
        return None

    # Enumerate instead of returning ``directory / name`` after is_file().
    # On case-insensitive filesystems (notably default macOS/Windows), that
    # synthetic Path can exist while carrying casing that differs from the
    # real directory entry. Returning the entry itself keeps behavior stable
    # across platforms and makes diagnostics show the actual filename.
    target = name.casefold()
    folded_match = None
    for child in directory.iterdir():
        if not child.is_file():
            continue
        if child.name == name:
            return child
        if folded_match is None and child.name.casefold() == target:
            folded_match = child
    return folded_match


def _canonical_file(path: Path) -> Path | None:
    """Resolve a file path while preserving the actual final-component casing."""
    return _case_insensitive_child(path.parent, path.name)


def resolve_mission_trn(
    bzn_path: os.PathLike | str,
    terrain_name: str | None = None,
) -> Path | None:
    """Resolve the terrain config referenced by BZN TerrainName, then same-stem fallback."""
    bzn = Path(bzn_path)
    directory = bzn.parent
    candidates: list[str] = []

    if terrain_name:
        normalized = _clean_bzn_value(terrain_name).replace("\\", "/")
        terrain_path = Path(normalized)
        names = [normalized, terrain_path.name]
        for name in names:
            if not name:
                continue
            candidates.append(name)
            if Path(name).suffix.lower() != ".trn":
                candidates.append(name + ".trn")

    candidates.append(bzn.stem + ".trn")

    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)

        candidate_path = Path(candidate)
        if candidate_path.is_absolute():
            resolved = _canonical_file(candidate_path)
            if resolved is not None:
                return resolved
            continue

        # Try the referenced relative path first, while returning the actual
        # on-disk entry rather than a synthetic differently-cased Path.
        relative = directory / candidate_path
        resolved = _canonical_file(relative)
        if resolved is not None:
            return resolved

        # If TerrainName carried a directory component that is not present in
        # the extracted package, also try its basename next to the BZN.
        sibling = _case_insensitive_child(directory, candidate_path.name)
        if sibling is not None:
            return sibling

    return None


def resolve_companion_hg2(trn_path: os.PathLike | str | None) -> Path | None:
    if not trn_path:
        return None
    trn = Path(trn_path)
    return _case_insensitive_child(trn.parent, trn.stem + ".hg2")
