# Battlezone98Redux World Builder v1.0.10

## Summary

v1.0.10 expands the Legacy Atlas workflow into a practical companion for porting authored Battlezone 1.5 terrain into Redux without launching each mission through the game first.

## Legacy HGT -> Redux HG2

- Adds authored `.HGT` -> `.HG2` conversion using the recovered Battlezone legacy terrain upgrade path.
- Matches the `-nohgtsmoothing` behavior: low 12-bit source heights are preserved, the legacy 128-sample-per-zone terrain is upgraded to Redux's 256-sample-per-zone grid with the recovered triangle interpolation, and the post-upgrade 3x3 smoothing pass is skipped.
- Applies no Gaussian filtering, height renormalization, or unrelated image resampling.
- Writes canonical Redux HG2 files using the existing HG2 codec.

## Bulk Legacy Mission Porting

- `CONVERT & BUILD ATLAS` now automatically scans the selected legacy source folder for authored HGT files and converts them alongside the texture/material port.
- Supports multiple mission terrain sets in one folder, such as `mission01.bzn/.trn/.hgt` through `mission10.bzn/.trn/.hgt`.
- Pairs each HGT with its same-stem TRN first so each mission can derive its own terrain dimensions independently.
- Retains a single-TRN fallback for simple one-world source folders.
- Generates one matching HG2 per authored HGT while the shared Redux atlas/material assets are built once.
- Keeps a manual single-HGT converter on the Legacy Atlas page as an advanced fallback.

## Compatibility

- Existing MakeTRN-compatible HGT import behavior remains smoothed by default; the new no-smoothing path is explicit and isolated.
- This release does not rewrite BZN mission logic or attempt to comprehensively modernize every legacy TRN field.

## Validation

- Added regression tests for unsmoothed triangle interpolation, legacy smoothed compatibility, HGT/HG2 round-trip output, the smoothing switch, and multi-mission same-stem HGT/TRN pairing.
- The full Windows, Linux, and macOS CI matrix passes.

## Downloads

- `world-builder-windows.exe` — Windows standalone GUI build
- `world-builder-linux` — Linux standalone GUI build
- `world-builder-macos.zip` — complete macOS application bundle
