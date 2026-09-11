# MAT format and Auto-Painter validation

Validated against:

- Battlezone MAT format reference: <https://battlezone.videoventure.org/format_mat.html>
- Battlezone TRN format reference: <https://battlezone.videoventure.org/format_trn.html>
- `BZMapIO.py` supplied as the behavior/reference implementation.

## Canonical MAT layout

A `.mat` has no header. It is a sequence of zone material blocks.

- One zone = `64 x 64` material entries = `4096` entries.
- One entry = 16 bits / 2 bytes.
- Zones are stored row-major from the southwest: west-to-east, then south-to-north.
- Entries inside a zone follow the same southwest-origin row-major convention.
- Therefore expected size is `zones_x * zones_z * 4096 * 2` bytes.

The material entry is:

| Bits | Meaning |
| --- | --- |
| 0-1 | Variant (0..3 / A..D) |
| 2-3 | Reserved / unused |
| 4-5 | Rotation |
| 6 | Flip |
| 7 | Cap selector: 0=Cap, 1=Diagonal |
| 8-11 | Next material |
| 12-15 | Base material |

On disk it is little-endian. Equivalently, the first byte is `(Mix << 4) | Variant` and the second byte is `(Base << 4) | Next`, where `Mix = (Cap << 3) | (Flip << 2) | Rotation`.

This matches `BZMapIO.py`'s two-byte writer. `BZMapIO.py` also reconstructs larger maps in 64x64 zone blocks rather than writing one global row-major matrix.

## BZMapIO variant discrepancy

The published MAT/TRN documentation defines four variants A-D using bits 0-1. `BZMapIO.py` historically treats the entire low nibble as a variant and includes values beyond D. Bits 2-3 are documented as unused, so WorldBuilder does **not** generate those legacy/non-standard values.

`mat_codec.decode_entry()` still exposes bits 2-3 as `reserved` so anomalous existing files can be diagnosed without pretending they are standard variants.

## Auto-Painter corrections

The old Auto-Painter had several independent format/behavior problems:

1. It generated MAT resolution as `heightmap / 2`. Redux HG2 normally has 256 samples per zone, but MAT is always 64 entries per zone. MAT resolution is now derived from zone count, not raw heightmap dimensions.
2. It wrote the whole NumPy matrix directly. Multi-zone MAT files require zone-major 64x64 blocks. Output now uses explicit zone packing.
3. It used native-endian `numpy.tobytes()`. Output now explicitly serializes little-endian 16-bit entries.
4. Its marching-square interpretation reversed Cap and Diagonal semantics. `BZMapIO.py` paints Caps along straight edges and Diagonals at corners. The new Mix mapping follows BZMapIO's actual paint/export rotations.
5. Checkerboard/saddle cases and >2-material junctions cannot be represented by one valid BZ transition tile. They now fall back to material 0 rather than inventing a transition.
6. TRN transitions are directional (`TextureTypeX -> CapToY/DiagonalToY`). When a TRN is loaded, the painter validates the direction before emitting a transition and falls back safely when the required pair is unavailable.
7. Slope was `atan(raw height delta)`, ignoring the 0.1m vertical scale and world-space sample spacing. It is now calculated in physical units.
8. Painter elevation units are now consistently MakeTRN decimeters (`0..4095`, i.e. `0..409.5m`). Auto-Balance previously mixed meters and raw values.
9. Loading a TRN no longer creates one full-range rule for every TextureType. It loads real `[Layer0]..[Layer7]` rules when present; otherwise existing rules are kept while TextureType/transition metadata is loaded for validation.
10. Direct `.hg2` and `.hgt` painter inputs are decoded as terrain files rather than being handed to Pillow as images.

## BZMapIO-derived Mix orientation

For the painter's data-space axes (`+X` east, `+Z` north), the reference behavior maps transitions as follows:

### Cap / straight edge

- Next material east (`+X`): Mix 6
- Next material west (`-X`): Mix 4
- Next material north (`+Z`): Mix 5
- Next material south (`-Z`): Mix 7

### Diagonal / corner

- Next material southwest: Mix 13
- Next material northwest: Mix 14
- Next material northeast: Mix 15
- Next material southeast: Mix 12

These values are derived from BZMapIO's paint-neighbor grouping plus its UV rotation/export mapping, rather than guessed from screen-space image orientation.

## Tests

`tests/test_mat_codec.py` covers:

- Known bitfield/byte encoding.
- Reserved-bit handling and the 0..3 standard variant range.
- 1-zone and multi-zone size/order.
- Pack/unpack round trips.
- BZMapIO Cap/Diagonal Mix mapping.
- Directional TRN transition validation.
- Physical slope calculation.
- 64x64 MAT-per-zone generation.
- `[LayerN]`, TextureType, transition, and Size parsing from TRN.

The codec is intentionally standalone so MAT correctness can be regression-tested without starting Tkinter/WorldBuilder.
