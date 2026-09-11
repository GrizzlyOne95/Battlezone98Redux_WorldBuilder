# Battlezone98Redux World Builder v1.0.5

## Summary

This release rolls the validated HG2, Mission Visualizer, and MAT Auto-Painter work into the packaged World Builder builds.

## Added

- Mission Visualizer terrain registration helpers for mapping BZN mission coordinates onto HG2 terrain correctly.
- Companion TRN/HG2 resolution with case-insensitive path handling across Windows, Linux, and macOS.
- MAT codec support and validated Auto-Painter generation based on Battlezone/MakeTRN material-map behavior.
- TRN painter configuration loading, directional transition handling, paint-rule validation, and Auto-Painter diagnostics.
- Unit coverage for Mission Visualizer registration and MAT codec behavior.

## Fixed

- Mission Visualizer HG2 orientation is displayed north-up while preserving Battlezone world-coordinate semantics.
- Mission overlays now use authoritative TRN/HG2 world dimensions instead of relying on a square preset guess.
- Non-zero MinX/MinZ terrain origins and rectangular terrain dimensions are respected when plotting mission objects and AI paths.
- Companion terrain files are resolved reliably even when filename casing differs between the BZN/TRN references and files on disk.
- Auto-Painter now writes MAT data through the validated MAT writer rather than dumping a raw NumPy byte array.
- Auto-Painter now uses HG2/HGT/image zone geometry and MakeTRN-compatible height/slope units.

## Downloads

- `world-builder-windows.exe` — Windows standalone build
- `world-builder-linux` — Linux standalone build
- `world-builder-macos.zip` — complete macOS application bundle

## Notes

Mission Visualizer BZN parsing currently targets ASCII BZN mission files. Binary BZN support remains a separate parser/integration task.
