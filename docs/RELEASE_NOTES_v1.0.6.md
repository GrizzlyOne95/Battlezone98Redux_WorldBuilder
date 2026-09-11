# Battlezone98Redux World Builder v1.0.6

## Summary

v1.0.6 expands the MakeTRN replacement work from MAT auto-painting into the broader MakeTRN 2.1.2 terrain-creation surface. Stock Map Creator now follows the recovered executable behavior for terrain geometry and legacy command semantics, and World Builder gains an open-source Interstate '76 MSN+TER conversion path.

This release builds on v1.0.5's validated MAT painter with canonical HG2/MAT geometry, configurable width and depth, EmptyElevation handling, legacy parameter-file behavior, runtime MAT variation, HGT terrain conversion support, and recovered MakeTRN MSN import behavior.

## Added

- MakeTRN 2.1.2 compatibility core shared by terrain-generation paths.
- Stock Map Creator support for independent terrain width and depth matching MakeTRN `/w` and `/h` semantics.
- EmptyElevation behavior compatible with MakeTRN `/e` handling.
- MakeTRN-style `[LayerN]` parameter-file support through the shared painter/compatibility core.
- Legacy runtime-random MAT texture variants while retaining deterministic modes for testing and reproducible builds.
- Open-source Interstate '76 `.MSN` + `.TER` terrain converter via `msn2terrain.py`.
- Recovery of Interstate '76 `TDEF/ZMAP` layout, occupied-zone cropping, TER block import, and source-origin preservation through TRN `MinX`/`MinZ`.
- Converter support for `/p=layers.ini` and `/e=N` compatibility aliases.
- HGT conversion support integrated with the MakeTRN-compatible terrain path.
- Executable-level MakeTRN research and parity documentation in `docs/MAKETRN_REVERSE_ENGINEERING.md`.
- Regression suites for MakeTRN compatibility, Stock Map Creator, MSN/TER decoding, and end-to-end MSN terrain conversion.

## Changed

- Stock Map Creator blank terrain generation now emits a complete TRN + HG2 + MAT set in one operation.
- HG2 output uses canonical Redux geometry with 256x256 samples per zone.
- MAT output continues to use the recovered MakeTRN/BZMapIO-compatible 64x64 entries per terrain zone.
- Terrain creation paths now use the recovered MakeTRN compatibility behavior instead of approximating legacy semantics independently.
- CI now includes the new MakeTRN compatibility and terrain-conversion modules.

## Interstate '76 conversion

Example:

```powershell
python msn2terrain.py mission.MSN --output Export --name I76MAP
```

The converter reads the Interstate '76 mission terrain definition, crops the occupied zone rectangle, imports the corresponding 256x256 TER blocks, preserves map origin information, and writes Battlezone Redux TRN + HG2 + MAT output through the same compatibility core used by World Builder.

## Downloads

- `world-builder-windows.exe` — Windows standalone GUI build
- `world-builder-linux` — Linux standalone GUI build
- `world-builder-macos.zip` — complete macOS application bundle
- Source archives include the MakeTRN compatibility modules and `msn2terrain.py` converter.

## Documentation

See `docs/MAKETRN_REVERSE_ENGINEERING.md` for the recovered MakeTRN 2.1.2 behavior and parity matrix, and `docs/MAT_FORMAT_VALIDATION.md` for the MAT format and painter semantics established in v1.0.5.
