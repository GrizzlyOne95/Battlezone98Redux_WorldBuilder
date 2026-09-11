# Battlezone98Redux World Builder v1.0.5

## Summary

v1.0.5 turns the Auto-Painter into a validated open-source replacement for MakeTRN's `/p=` material-painting workflow while also packaging the recent HG2 and Mission Visualizer fixes.

The GUI and command-line painter now share one reverse-engineered `mat_codec.py` implementation, with compatibility behavior documented and regression-tested against the historical MakeTRN executable and BZMapIO conventions.

## Added

- MakeTRN-compatible MAT painting core with exact recovered layer ordering, inclusive elevation/slope ranges, coarse 4x4 HG2 sampling cadence, transition synthesis, material fallback behavior, and legacy MSVCR120 texture-variant randomization.
- Standalone `bzpaint.py` command-line frontend using the same painter core as World Builder.
- Legacy-style command syntax such as `python bzpaint.py mapname.trn /p=moon.ini` and `/e=...`.
- Modern CLI options including deterministic `--seed`, `--dry-run`, `--json`, `--params`, and `--output`.
- BZMapIO-compatible MAT read/write handling with validated 64x64-per-zone storage and zone-major serialization.
- MakeTRN `[Layer0]` through `[Layer7]` configuration parsing with first-match-wins semantics.
- TRN CapTo/DiagonalTo transition diagnostics without mutating generated MAT data.
- Detailed MAT/MakeTRN reverse-engineering documentation in `docs/MAT_FORMAT_VALIDATION.md`.
- Mission Visualizer terrain registration helpers for correctly mapping BZN mission coordinates onto HG2 terrain.
- Companion TRN/HG2 resolution with case-insensitive path handling across Windows, Linux, and macOS.
- Expanded regression coverage for HG2 masking, MAT packing, MakeTRN slope/elevation calculations, transition patterns, randomization, and CLI behavior.

## Fixed

- Auto-Painter no longer uses generic gradient-based slope estimation; it reproduces MakeTRN's local maximum edge-delta calculation and legacy angle conversion.
- Auto-Painter now uses MakeTRN's recovered elevation rule calculation rather than mixing display/world height units into painter rules.
- Rule evaluation now uses the historical first-matching-layer behavior with inclusive bounds.
- MAT generation now produces 64x64 entries per Redux terrain zone and writes proper zone-major output instead of dumping a raw NumPy array.
- Cap, diagonal, rotation, mirror, base/next material, and variant fields now follow the recovered MakeTRN/BZMapIO-compatible 16-bit encoding.
- Unsupported two-material corner patterns and three-or-more-material intersections now collapse the same way as MakeTRN.
- Mission Visualizer HG2 orientation is displayed north-up while preserving Battlezone world-coordinate semantics.
- Mission overlays use authoritative TRN/HG2 dimensions, non-zero MinX/MinZ origins, and rectangular terrain geometry.
- Companion terrain files resolve reliably even when reference/file casing differs.

## Compatibility notes

- The historical MakeTRN help text claims a 10-degree default slope split, but the executable actually uses 15 degrees. World Builder reproduces the executable behavior.
- MakeTRN seeded texture variation from `clock()`. World Builder and `bzpaint.py` default to a fixed seed for reproducible output while retaining the recovered MSVCR120 transformation logic.
- World Builder follows BZMapIO's canonical 13-bit HG2 height interpretation rather than reproducing undefined behavior from stray high bits in malformed HG2 samples.
- BZN/image masks, deterministic output, validation, previews, and diagnostics are World Builder extensions layered on top of the MakeTRN-compatible core.

## Downloads

- `world-builder-windows.exe` — Windows standalone GUI build
- `world-builder-linux` — Linux standalone GUI build
- `world-builder-macos.zip` — complete macOS application bundle
- Source archives include `bzpaint.py` for command-line use.

## Documentation

See `docs/MAT_FORMAT_VALIDATION.md` for the recovered MAT format, MakeTRN layer semantics, slope/elevation calculations, transition encoding, and compatibility decisions.

Mission Visualizer BZN parsing currently targets ASCII BZN mission files. Binary BZN support remains a separate parser/integration task.
