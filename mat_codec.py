from __future__ import annotations
import math
import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional
import numpy as np
from PIL import Image, ImageDraw
MAT_ZONE_SIZE = 64
MAT_ENTRY_BYTES = 2
HG2_SAMPLES_PER_ZONE = 256
MAKE_TRN_SAMPLE_STEP = 4
MAKE_TRN_LAYER_LIMIT = 8
MAKE_TRN_ELEVATION_DIVISOR = 5
MAKE_TRN_SLOPE_DENOMINATOR = 50.0
MAKE_TRN_DEGREES_PER_RADIAN = 57.295780181884766
PAINTER_MAX_MATERIAL = 7
PAINTER_MAX_ELEVATION = 4095.0
PAINTER_MAX_ELEVATION_DM = PAINTER_MAX_ELEVATION
WORLD_ZONE_METERS = 1280.0

@dataclass(frozen=True)
class MatEntry:
    base: int
    next: int
    cap: int
    flip: int
    rotation: int
    variant: int

    @property
    def mix(self):
        return (self.cap & 1) << 3 | (self.flip & 1) << 2 | self.rotation & 3

    @property
    def documented_variant(self):
        return self.variant & 3

    @property
    def reserved(self):
        return self.variant >> 2 & 3

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
    cap_transitions: frozenset[tuple[int, int]]
    diagonal_transitions: frozenset[tuple[int, int]]
    min_x: float = 0.0
    min_z: float = 0.0
    width: Optional[float] = None
    depth: Optional[float] = None

    @property
    def transitions(self):
        return self.cap_transitions | self.diagonal_transitions

class MakeTRNRuleError(ValueError):

    def __init__(self, x,iz, elevation, slope):
        super().__init__(f'MakeTRN-compatible painter found no valid layer at x={x}, z={z}: elevation={elevation}, slope={slope}')
        self.x = x
        self.z = z
        self.elevation = elevation
        self.slope = slope

class MSVCRand:

    def __init__(self, seed=1):
        self.state = int(seed) & 4294967295

    def rand(self):
        self.state = self.state * 214013 + 2531011 & 4294967295
        return self.state >> 16 & 32767

def _check_range(name, value, low, high):
    if not low <= int(value) <= high:
        raise ValueError(f'{name} must be in {low}..{high}, got {value}')

def encode_entry(base, next_mat, cap=0, flip=0, rotation=0, variant=0, reserved=None):
    _check_range('base', base, 0, 15)
    _check_range('next_mat', next_mat, 0, 15)
    _check_range('cap', cap, 0, 1)
    _check_range('flip', flip, 0, 1)
    _check_range('rotation', rotation, 0, 3)
    if reserved is None:
        _check_range('variant', variant, 0, 15)
        low = int(variant) & 15
    else:
        _check_range('variant', variant, 0, 3)
        _check_range('reserved', reserved, 0, 3)
        low = int(variant) & 3 | (int(reserved) & 3) << 2
    mix = (int(cap) & 1) << 3 | (int(flip) & 1) << 2 | int(rotation) & 3
    return low | (mix & 15) << 4 | (int(next_mat) & 15) << 8 | (int(base) & 15) << 12

def encode_mix_entry(base, next_mat, mix, variant=0):
    _check_range('mix', mix, 0, 15)
    return encode_entry(base=base, next_mat=next_mat, cap=mix >> 3 & 1, flip=mix >> 2 & 1, rotation=mix & 3, variant=variant)

def decode_entry(value):
    _check_range('MAT entry', value, 0, 65535)
    mix = int(value) >> 4 & 15
    return MatEntry(base=int(value) >> 12 & 15, next=int(value) >> 8 & 15, cap=mix >> 3 & 1, flip=mix >> 2 & 1, rotation=mix & 3, variant=int(value) & 15)

def entry_to_bytes(value):
    _check_range('MAT entry', value, 0, 65535)
    return int(value).to_bytes(2, 'little')

def entry_from_bytes(raw):
    if len(raw) != 2:
        raise ValueError('A MAT entry is exactly two bytes')
    return int.from_bytes(raw, 'little')

def expected_mat_bytes(zones_x, zones_z):
    if zones_x <= 0 or zones_z <= 0:
        raise ValueError('MAT zone dimensions must be positive')
    return zones_x * zones_z * MAT_ZONE_SIZE * MAT_ZONE_SIZE * MAT_ENTRY_BYTES

def pack_mat_zones(entries, zones_x, zones_z):
    array = np.asarray(entries)
    expected_shape = (zones_z * MAT_ZONE_SIZE, zones_x * MAT_ZONE_SIZE)
    if array.shape != expected_shape:
        raise ValueError(f'MAT shape {array.shape} does not match {expected_shape}')
    if array.size and (np.min(array) < 0 or np.max(array) > 65535):
        raise ValueError('MAT entries must fit in uint16')
    encoded = np.rint(array).astype('<u2')
    output = bytearray(expected_mat_bytes(zones_x, zones_z))
    cursor = 0
    zone_bytes = MAT_ZONE_SIZE * MAT_ZONE_SIZE * MAT_ENTRY_BYTES
    for zone_z in range(zones_z):
        for zone_x in range(zones_x):
            z0 = zone_z * MAT_ZONE_SIZE
            x0 = zone_x * MAT_ZONE_SIZE
            zone = encoded[z0:z0 + MAT_ZONE_SIZE, x0:x0 + MAT_ZONE_SIZE]
            raw = zone.astype('<u2', copy=False).tobytes(order='C')
            output[cursor:cursor + zone_bytes] = raw
            cursor += zone_bytes
    return bytes(output)

def unpack_mat_zones(payload, zones_x, zones_z):
    expected = expected_mat_bytes(zones_x, zones_z)
    if len(payload) != expected:
        raise ValueError(f'MAT size mismatch: expected {expected} bytes, found {len(payload)}')
    raw = np.frombuffer(payload, dtype='<u2')
    full = np.empty((zones_z * MAT_ZONE_SIZE, zones_x * MAT_ZONE_SIZE), dtype=np.uint16)
    cursor = 0
    zone_entries = MAT_ZONE_SIZE * MAT_ZONE_SIZE
    for zone_z in range(zones_z):
        for zone_x in range(zones_x):
            zone = raw[cursor:cursor + zone_entries].reshape((MAT_ZONE_SIZE, MAT_ZONE_SIZE))
            z0 = zone_z * MAT_ZONE_SIZE
            x0 = zone_x * MAT_ZONE_SIZE
            full[z0:z0 + MAT_ZONE_SIZE, x0:x0 + MAT_ZONE_SIZE] = zone
            cursor += zone_entries
    return full

def write_mat(path, entries, zones_x, zones_z):
    with open(path, 'wb') as stream:
        stream.write(pack_mat_zones(entries, zones_x, zones_z))

def read_mat(path, zones_x, zones_z):
    with open(path, 'rb') as stream:
        return unpack_mat_zones(stream.read(), zones_x, zones_z)

def _numeric(value):
    match = re.search('[-+]?\\d+(?:\\.\\d+)?(?:[eE][-+]?\\d+)?', value)
    if not match:
        raise ValueError(f'not a numeric value: {value!r}')
    return float(match.group(0))

def _legacy_int(value, default):
    try:
        return int(_numeric(value))
    except (ValueError, TypeError):
        return int(default)

def parse_trn_painter(path):
    sections: dict[str, list[tuple[str, str]]] = {}
    current = ''
    with open(path, 'r', encoding='cp1252', errors='replace') as stream:
        for original in stream:
            line = original.strip()
            if not line or line.startswith('//') or line.startswith(';'):
                continue
            if line.startswith('[') and line.endswith(']'):
                current = line[1:-1].strip()
                sections.setdefault(current, [])
                continue
            if '=' in line and current:
                key, value = line.split('=', 1)
                sections.setdefault(current, []).append((key.strip(), value.strip()))
    size_values = {'minx': 0.0, 'minz': 0.0, 'width': None, 'depth': None}
    texture_types: set[int] = set()
    cap_transitions: set[tuple[int, int]] = set()
    diagonal_transitions: set[tuple[int, int]] = set()
    layer_rows: list[tuple[int, dict]] = []
    for section, items in sections.items():
        lower = section.lower()
        values = {k.lower(): v for k, v in items}
        if lower == 'size':
            for key in size_values:
                if key in values:
                    try:
                        size_values[key] = _numeric(values[key])
                    except ValueError:
                        pass
            continue
        tex_match = re.fullmatch('texturetype(\\d+)', lower)
        if tex_match:
            base = int(tex_match.group(1))
            texture_types.add(base)
            for key, _ in items:
                cap_match = re.match('capto(\\d+)_', key, re.IGNORECASE)
                diag_match = re.match('diagonalto(\\d+)_', key, re.IGNORECASE)
                if cap_match:
                    cap_transitions.add((base, int(cap_match.group(1))))
                if diag_match:
                    diagonal_transitions.add((base, int(diag_match.group(1))))
            continue
        layer_match = re.fullmatch('layer(\\d+)', lower)
        if layer_match:
            index = int(layer_match.group(1))
            if index >= MAKE_TRN_LAYER_LIMIT:
                continue
            material = _legacy_int(values.get('material', '8'), 8)
            if material >= 8:
                continue
            layer_rows.append((index, {'mat_id': material, 'min_h': _legacy_int(values.get('elevationstart', '4095'), 4095), 'max_h': _legacy_int(values.get('elevationend', '4095'), 4095), 'min_s': _legacy_int(values.get('slopestart', '90'), 90), 'max_s': _legacy_int(values.get('slopeend', '90'), 90), 'mask_path': ''}))
    layer_rows.sort(key=lambda item: item[0])
    return TRNPainterConfig(layers=tuple((row for _, row in layer_rows)), texture_types=tuple(sorted(texture_types)), cap_transitions=frozenset(cap_transitions), diagonal_transitions=frozenset(diagonal_transitions), min_x=float(size_values['minx'] or 0.0), min_z=float(size_values['minz'] or 0.0), width=size_values['width'], depth=size_values['depth'])

def default_make_trn_rules():
    return [{'mat_id': 0, 'min_h': 0, 'max_h': 4095, 'min_s': 0, 'max_s': 15, 'mask_path': ''}, {'mat_id': 3, 'min_h': 0, 'max_h': 4095, 'min_s': 15, 'max_s': 90, 'mask_path': ''}]

def validate_paint_rules(rules):
    warnings: list[str] = []
    rules = list(rules)
    if not rules:
        return ['No paint rules are defined.']
    if len(rules) > MAKE_TRN_LAYER_LIMIT:
        warnings.append(f'MakeTRN supports at most {MAKE_TRN_LAYER_LIMIT} layers; found {len(rules)}')
    for i, rule in enumerate(rules):
        try:
            mat_id = int(rule['mat_id'])
            min_h, max_h = (int(float(rule['min_h'])), int(float(rule['max_h'])))
            min_s, max_s = (int(float(rule['min_s'])), int(float(rule['max_s'])))
        except (KeyError, TypeError, ValueError):
            warnings.append(f'Rule {i}: malformed numeric fields')
            continue
        if not 0 <= mat_id <= PAINTER_MAX_MATERIAL:
            warnings.append(f'Rule {i} (Mat{mat_id}): painter material must be 0..{PAINTER_MAX_MATERIAL}')
        if min_h > max_h:
            warnings.append(f'Rule {i} (Mat{mat_id}): ElevationStart > ElevationEnd')
        if min_s > max_s:
            warnings.append(f'Rule {i} (Mat{mat_id}): SlopeStart > SlopeEnd')
        if min_s < 0 or max_s > 90:
            warnings.append(f'Rule {i} (Mat{mat_id}): normal MakeTRN slope range is 0..90 degrees')
        mask_path = str(rule.get('mask_path', '') or '')
        if mask_path and (not mask_path.upper().startswith('PATH:')) and (not os.path.exists(mask_path)):
            warnings.append(f'Rule {i} (Mat{mat_id}): mask file does not exist: {mask_path}')
    return warnings

def _signed_word(value):
    value = int(value) & 65535
    return value - 65536 if value & 32768 else value

def _sample(height, x, z, fallback):
    if 0 <= z < height.shape[0] and 0 <= x < height.shape[1]:
        return _signed_word(int(height[z, x]))
    return int(fallback)

def make_trn_metrics_at(height_raw, x, z, fallback_elevation=0):
    height = np.asarray(height_raw)
    if height.ndim != 2:
        raise ValueError('height data must be a 2-D array')
    minimum = _sample(height, x, z, fallback_elevation)
    for dz in range(-4, 4):
        for dx in range(-4, 4):
            minimum = min(minimum, _sample(height, x + dx, z + dz, fallback_elevation))
    max_delta = 0
    for dz in range(-4, 4):
        for dx in range(-4, 4):
            a = _sample(height, x + dx, z + dz, fallback_elevation)
            b = _sample(height, x + dx + 1, z + dz, fallback_elevation)
            c = _sample(height, x + dx + 1, z + dz + 1, fallback_elevation)
            d = _sample(height, x + dx, z + dz + 1, fallback_elevation)
            max_delta = max(max_delta, abs(a - b), abs(b - c), abs(c - d), abs(d - a))
    elevation = math.trunc(minimum / MAKE_TRN_ELEVATION_DIVISOR)
    if max_delta == 0:
        slope = 0
    else:
        hyp = math.sqrt(float(max_delta * max_delta) + 2500.0)
        angle = math.asin(float(max_delta) / hyp) * MAKE_TRN_DEGREES_PER_RADIAN
        slope = math.trunc(angle)
    return (elevation, slope)

def calculate_slope_degrees(height_raw, zones_x, zones_z):
    height = np.asarray(height_raw)
    _validate_make_trn_geometry(height, zones_x, zones_z)
    out = np.empty((zones_z * MAT_ZONE_SIZE, zones_x * MAT_ZONE_SIZE), dtype=np.float32)
    for mz in range(out.shape[0]):
        for mx in range(out.shape[1]):
            _, slope = make_trn_metrics_at(height, mx * 4, mz * 4)
            out[mz, mx] = slope
    return out

def _rasterize_path_mask(h, w, bzn_paths, label, min_x, min_z, world_width, world_depth):
    target = next((p for p in bzn_paths if p.get('label') == label), None)
    if not target or not target.get('points') or world_width <= 0 or (world_depth <= 0):
        return np.zeros((h, w), dtype=bool)
    image = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(image)
    points = []
    for px_world, pz_world in target['points']:
        px = (float(px_world) - min_x) / world_width * w
        pz = (float(pz_world) - min_z) / world_depth * h
        points.append((px, pz))
    if target.get('type') == 3 and len(points) >= 3:
        draw.polygon(points, fill=255)
    elif len(points) >= 2:
        draw.line(points, fill=255, width=max(1, round(min(h, w) / 128)))
    return np.asarray(image) > 127

def _prepare_rule_masks(height_shape, rules, bzn_paths, min_x, min_z, world_width, world_depth):
    h, w = height_shape
    result: list[Optional[np.ndarray]] = []
    for rule in rules:
        mask_path = str(rule.get('mask_path', '') or '')
        if not mask_path:
            result.append(None)
            continue
        if mask_path.upper().startswith('PATH:'):
            label = mask_path.split(':', 1)[1]
            result.append(_rasterize_path_mask(h, w, bzn_paths, label, min_x, min_z, world_width, world_depth))
            continue
        image = Image.open(mask_path).convert('L')
        if image.size != (w, h):
            image = image.resize((w, h), Image.Resampling.NEAREST)
        result.append(np.asarray(image) > 127)
    return result

def _validate_make_trn_geometry(height, zones_x, zones_z):
    if height.ndim != 2:
        raise ValueError('height data must be two-dimensional')
    expected = (zones_z * HG2_SAMPLES_PER_ZONE, zones_x * HG2_SAMPLES_PER_ZONE)
    if height.shape != expected:
        raise ValueError(f'MakeTRN-compatible Redux painting expects {expected[1]}x{expected[0]} HG2 samples for {zones_x}x{zones_z} zones; found {height.shape[1]}x{height.shape[0]}')

def classify_samples(height_raw, rules, zones_x, zones_z, bzn_paths=None, min_x=0.0, min_z=0.0, world_width=None, world_depth=None, fallback_elevation=0, strict=True):
    height = np.asarray(height_raw)
    _validate_make_trn_geometry(height, zones_x, zones_z)
    rules = list(rules)[:MAKE_TRN_LAYER_LIMIT]
    if not rules:
        rules = default_make_trn_rules()
    bzn_paths = bzn_paths or []
    world_width = float(world_width or zones_x * WORLD_ZONE_METERS)
    world_depth = float(world_depth or zones_z * WORLD_ZONE_METERS)
    masks = _prepare_rule_masks(height.shape, rules, bzn_paths, min_x, min_z, world_width, world_depth)
    coarse_h = zones_z * MAT_ZONE_SIZE
    coarse_w = zones_x * MAT_ZONE_SIZE
    materials = np.zeros((coarse_h, coarse_w), dtype=np.uint8)
    unmatched = 0
    for mz in range(coarse_h):
        z = mz * MAKE_TRN_SAMPLE_STEP
        for mx in range(coarse_w):
            x = mx * MAKE_TRN_SAMPLE_STEP
            elevation, slope = make_trn_metrics_at(height, x, z, fallback_elevation)
            chosen: Optional[int] = None
            for index, rule in enumerate(rules):
                min_h = int(float(rule['min_h']))
                max_h = int(float(rule['max_h']))
                min_s = int(float(rule['min_s']))
                max_s = int(float(rule['max_s']))
                if not (min_h <= elevation <= max_h and min_s <= slope <= max_s):
                    continue
                mask = masks[index]
                if mask is not None and (not bool(mask[z, x])):
                    continue
                mat_id = int(rule['mat_id'])
                if not 0 <= mat_id <= PAINTER_MAX_MATERIAL:
                    if strict:
                        raise MakeTRNRuleError(x, z, elevation, slope)
                    continue
                chosen = mat_id
                break
            if chosen is None:
                unmatched += 1
                if strict:
                    raise MakeTRNRuleError(x, z, elevation, slope)
                chosen = 0
            materials[mz, mx] = chosen
    return (materials, unmatched)
_MAKE_TRN_MIX_BY_PATTERN = {3: 0, 6: 1, 12: 2, 9: 3, 7: 8, 14: 9, 13: 10, 11: 11}

def _legacy_variant_from_rand(value):
    low = int(value) & 15
    if low >= 8:
        return 0
    if low >= 4:
        return 1
    if low >= 2:
        return 2
    return 3

def encode_make_trn_tile(corners, rng=None):
    if len(corners) != 4:
        raise ValueError('MakeTRN tile encoding requires four corner materials')
    values = tuple((int(v) for v in corners))
    for value in values:
        _check_range('material', value, 0, 7)
    minimum = min(values)
    maximum = max(values)
    pattern = 0
    for bit, value in enumerate(values):
        if value != minimum:
            pattern |= 1 << bit
    ambiguous = any((value not in (minimum, maximum) for value in values))
    mix_base = _MAKE_TRN_MIX_BY_PATTERN.get(pattern)
    if ambiguous:
        base = next_mat = 7
        mix_base = 0
        kind = 'ambiguous'
    elif minimum == maximum:
        base = next_mat = minimum
        mix_base = None
        kind = 'solid'
    elif mix_base is None:
        base = next_mat = minimum
        kind = 'ambiguous'
    else:
        base, next_mat = (minimum, maximum)
        kind = 'diagonal' if mix_base >= 8 else 'cap'
    rng = rng or MSVCRand(1)
    random_value = rng.rand()
    mirror = random_value >> 2 & 4
    if base == next_mat:
        mix = random_value >> 13 | mirror
    else:
        mix = int(mix_base) | mirror
    variant = _legacy_variant_from_rand(random_value)
    return (encode_mix_entry(base, next_mat, mix, variant), kind)

def encode_transition_from_corners(corners, cap_transitions=None, diagonal_transitions=None, default_material=0):
    del cap_transitions, diagonal_transitions, default_material
    return encode_make_trn_tile(corners, MSVCRand(1))

def _coarse_material_at(materials, mx, mz):
    if 0 <= mz < materials.shape[0] and 0 <= mx < materials.shape[1]:
        return int(materials[mz, mx])
    return 0

def generate_mat(height_raw, rules, zones_x, zones_z, cap_transitions=None, diagonal_transitions=None, transitions=None, bzn_paths=None, min_x=0.0, min_z=0.0, world_width=None, world_depth=None, default_material=0, legacy_seed=1, fallback_elevation=0, strict=True):
    del default_material
    warnings = validate_paint_rules(rules)
    fatal = [warning for warning in warnings if 'malformed' in warning or 'must be 0..7' in warning or 'ElevationStart >' in warning or ('SlopeStart >' in warning) or ('at most' in warning) or ('does not exist' in warning)]
    if fatal:
        raise ValueError('; '.join(fatal))
    height = np.asarray(height_raw)
    _validate_make_trn_geometry(height, zones_x, zones_z)
    sample_mats, unmatched = classify_samples(height, rules, zones_x, zones_z, bzn_paths=bzn_paths, min_x=min_x, min_z=min_z, world_width=world_width, world_depth=world_depth, fallback_elevation=fallback_elevation, strict=strict)
    if transitions is not None and cap_transitions is None and (diagonal_transitions is None):
        cap_transitions = transitions
        diagonal_transitions = transitions
    caps = frozenset(cap_transitions or ())
    diagonals = frozenset(diagonal_transitions or ())
    validating_caps = cap_transitions is not None
    validating_diagonals = diagonal_transitions is not None
    out = np.empty((zones_z * MAT_ZONE_SIZE, zones_x * MAT_ZONE_SIZE), dtype=np.uint16)
    stats = PaintStats(total_tiles=out.size, unmatched_samples=unmatched)
    rng = MSVCRand(legacy_seed)
    for zone_z in range(zones_z):
        for zone_x in range(zones_x):
            for local_z in range(MAT_ZONE_SIZE):
                mz = zone_z * MAT_ZONE_SIZE + local_z
                for local_x in range(MAT_ZONE_SIZE):
                    mx = zone_x * MAT_ZONE_SIZE + local_x
                    corners = (_coarse_material_at(sample_mats, mx, mz), _coarse_material_at(sample_mats, mx + 1, mz), _coarse_material_at(sample_mats, mx + 1, mz + 1), _coarse_material_at(sample_mats, mx, mz + 1))
                    entry, kind = encode_make_trn_tile(corners, rng)
                    out[mz, mx] = entry
                    decoded = decode_entry(entry)
                    if kind == 'solid':
                        stats.solid_tiles += 1
                    elif kind == 'cap':
                        stats.cap_tiles += 1
                        if validating_caps and (decoded.base, decoded.next) not in caps:
                            stats.unsupported_transition_tiles += 1
                    elif kind == 'diagonal':
                        stats.diagonal_tiles += 1
                        if validating_diagonals and (decoded.base, decoded.next) not in diagonals:
                            stats.unsupported_transition_tiles += 1
                    else:
                        stats.ambiguous_tiles += 1
                        stats.solid_tiles += 1
    return (out, stats)
