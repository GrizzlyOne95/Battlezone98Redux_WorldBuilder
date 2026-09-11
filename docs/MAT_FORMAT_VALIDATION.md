# MAT format and MakeTRN Auto-Painter validation

Validated against:

- Battlezone MAT format reference: <https://battlezone.videoventure.org/format_mat.html>
- Battlezone TRN format reference: <https://battlezone.videoventure.org/format_trn.html>
- `BZMapIO.py`, used as the authoritative open-source MAT read/write cross-check.
- The historical `MakeTRN.exe` supplied for this investigation.

Exact MakeTRN binary used for reverse engineering:

```text
SHA-256 dc16de74f9d23e3ab6bd1c7d529f9b4dcef565e99f9b1bb5b8fda13a208b37c5
PE32 i386
```

The goal is behavioral compatibility with MakeTRN's automatic painting path, while keeping WorldBuilder-only features such as BZN masks, image masks, validation, previews, and deterministic output as clearly identified extensions.

## Canonical MAT layout

A `.mat` has no header. It is a sequence of zone material blocks.

- One zone = `64 x 64` material entries = `4096` entries.
- One entry = 16 bits / 2 bytes.
- One zone therefore occupies `8192` bytes.
- Zones are stored west-to-east and then south-to-north.
- Entries inside each 64x64 zone are row-major in the same terrain-space convention.
- Expected size is `zones_x * zones_z * 4096 * 2` bytes.

The 16-bit value is:

| Bits | Meaning |
| --- | --- |
| 0-3 | Variant nibble |
| 4-5 | Rotation |
| 6 | Flip/mirror |
| 7 | Cap/Diagonal selector |
| 8-11 | Next/to material |
| 12-15 | Base/from material |

On disk the uint16 is little-endian. Equivalently the first byte is `(Mix << 4) | Variant` and the second is `(Base << 4) | Next`, with `Mix = (Cap << 3) | (Flip << 2) | Rotation`.

### Public-spec variant discrepancy

The published MAT documentation describes bits 0-1 as a four-value A-D variant and bits 2-3 as unused. `BZMapIO.py`, however, reads and writes the entire low nibble as the variant and its variant table includes values beyond D. WorldBuilder therefore round-trips the full nibble `0..15` while exposing the documented low two bits separately for diagnostics.

This is an intentional BZMapIO-compatibility choice rather than silently discarding bits 2-3.

## MakeTRN layer file behavior

MakeTRN accepts up to eight sections:

```ini
[Layer0]
ElevationStart=0
ElevationEnd=4095
SlopeStart=0
SlopeEnd=15
Material=0
```

The recovered 20-byte layer record is:

```text
+00 ElevationStart
+04 ElevationEnd
+08 SlopeStart
+12 SlopeEnd
+16 Material
```

Behavior proven from the executable:

- `Layer0` through `Layer7` are supported.
- Material IDs must be `0..7`.
- Elevation and slope lower/upper bounds are all inclusive.
- Layers are tested in ascending order and the first matching layer wins.
- If no layer matches, MakeTRN reports the missing elevation/slope combination and aborts.
- Overlapping rules are therefore meaningful and deterministic.

### Actual built-in defaults

The binary initializes these defaults when no parameter file is supplied:

```ini
[Layer0]
ElevationStart=0
ElevationEnd=4095
SlopeStart=0
SlopeEnd=15
Material=0

[Layer1]
ElevationStart=0
ElevationEnd=4095
SlopeStart=15
SlopeEnd=90
Material=3
```

The executable's help text says the split is 10 degrees, but the machine code uses **15 degrees**. At exactly 15 degrees both rules match and first-match-wins selects Material 0.

## Exact MakeTRN terrain sampling

Redux HG2 uses 256 height samples per 1280 m zone. MakeTRN advances the painter lattice by four HG2 samples in each axis, producing exactly 64 material lattice points per zone.

For each coarse lattice point `(x,z)`, MakeTRN examines raw HG2 samples in the 8x8 neighborhood:

```text
dx = -4 .. +3
dz = -4 .. +3
```

Out-of-bounds elevation samples use MakeTRN's fallback elevation value (`-e`; default 0).

### Elevation rule value

MakeTRN finds the minimum raw HG2 value in that 8x8 neighborhood and compares:

```text
Elevation = trunc(minimum_raw_height / 5)
```

This is the legacy painter's own rule unit. It must **not** be replaced with BZMapIO's `/10` world/display conversion. Those are separate semantics.

### Slope rule value

Across the same local region, MakeTRN visits unit HG2 cells and measures the four orthogonal edge differences:

```text
A ---- B
|      |
|      |
D ---- C
```

For each cell it considers:

```text
abs(A-B)
abs(B-C)
abs(C-D)
abs(D-A)
```

The largest difference seen anywhere in the neighborhood becomes `delta`.

The binary then computes:

```text
slope = trunc(
    asin(delta / sqrt(delta*delta + 2500.0))
    * 57.295780181884766
)
```

which is mathematically equivalent to:

```text
trunc(degrees(atan(delta / 50.0)))
```

This is deliberately reproduced rather than using `numpy.gradient()` or another modern slope estimator.

## Exact MakeTRN transition synthesis

The classification stage first produces a 64-per-zone coarse material lattice. Final MAT entries are synthesized from four neighboring lattice materials:

```text
A = (x,   z)
B = (x+1, z)
C = (x+1, z+1)
D = (x,   z+1)
```

A material lookup outside the coarse grid returns Material 0, matching the binary.

For two-material cases, MakeTRN uses the minimum material as `Base` and maximum as `Next`. A four-bit pattern records which corners differ from the minimum material.

Recovered representable patterns:

| Pattern A/B/C/D | Mix | Family |
| --- | ---: | --- |
| `0011` | 0 | Cap |
| `0110` | 1 | Cap |
| `1100` | 2 | Cap |
| `1001` | 3 | Cap |
| `0111` | 8 | Diagonal |
| `1110` | 9 | Diagonal |
| `1101` | 10 | Diagonal |
| `1011` | 11 | Diagonal |

The single-high patterns `0001`, `0010`, `0100`, `1000` and checkerboards `0101`/`1010` do not have a legacy transition representation. MakeTRN collapses them to a solid minimum-material entry.

If three or four distinct materials meet at one tile, MakeTRN collapses the result to solid Material 7.

This behavior is intentionally preserved rather than replacing it with a generalized marching-squares interpretation.

## Legacy randomization

MakeTRN calls the MSVCR120 `rand()` implementation once for every output MAT tile. The CRT algorithm is:

```text
state = (state * 214013 + 2531011) & 0xFFFFFFFF
rand  = (state >> 16) & 0x7FFF
```

The random value controls:

- mirror/flip bit on transitions;
- otherwise visually irrelevant orientation bits on solids;
- texture variant selection.

The recovered A-D variant weighting is approximately:

- A / variant 0: 50%
- B / variant 1: 25%
- C / variant 2: 12.5%
- D / variant 3: 12.5%

The original executable seeds the CRT RNG from `clock()`, so repeated legacy runs are not byte-for-byte deterministic even when the visible material layout is equivalent. WorldBuilder defaults to seed `1` so builds are reproducible while retaining the same PRNG and per-tile transformation rules.

## TRN transition definitions

`TextureTypeN` sections can declare directional `CapToM_*` and `DiagonalToM_*` texture families. WorldBuilder parses these and reports transitions generated by the painter that do not have corresponding texture definitions.

This is **diagnostic only**. Missing texture metadata does not rewrite or replace the MAT entry, because MakeTRN's MAT synthesis itself does not perform that fallback.

## WorldBuilder extensions

The compatibility core remains separate from optional modern functionality:

- BZN `PATH:` masks.
- Raster/image masks.
- Image heightmap input, resampled explicitly to 256 HG2 samples per zone.
- Rule validation and transition diagnostics.
- Auto-Balance convenience rules.
- Deterministic RNG seed for reproducible builds.

Legacy HGT auto-painting is not silently resampled in compatibility mode. HGT must be converted to the canonical Redux HG2 geometry first, because resampling would no longer reproduce MakeTRN behavior.

## Regression coverage

`tests/test_mat_codec.py` locks down:

- full BZMapIO-compatible variant nibble round-trip;
- documented reserved-bit compatibility;
- 64x64 zone size and multi-zone byte ordering;
- 8x8 minimum-elevation sampling;
- maximum local edge-delta slope calculation;
- border fallback behavior;
- first-match-wins and inclusive layer bounds;
- the executable's real 15-degree default split;
- MSVCR120 random sequence;
- all eight recovered MakeTRN transition patterns;
- unsupported/checkerboard and three-material collapse behavior;
- random mirror/variant logic;
- MakeTRN `[LayerN]` parsing and TRN transition metadata.

The codec is standalone so the compatibility behavior can be regression-tested without starting Tkinter/WorldBuilder.
