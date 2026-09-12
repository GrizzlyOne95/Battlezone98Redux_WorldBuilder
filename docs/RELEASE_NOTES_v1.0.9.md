# Battlezone98Redux World Builder v1.0.9

## Summary

v1.0.9 makes the legacy Battlezone 1.5 -> Redux terrain conversion path produce a materially correct, usable Redux port instead of only generating superficially plausible files.

## Legacy Map Conversion

- Fixes BZ `.MAP` scanline orientation so legacy tiles are no longer vertically mirrored during conversion.
- Restores the expected south / southeast transition orientation used by Redux terrain atlas rotation.
- Emits the required `[Atlases]` TRN binding so the generated terrain material is actually selected by Redux.
- Names the generated atlas mapping CSV after the material, matching Redux lookup behavior.
- Resolves the palette from the source TRN `[Color] Palette=` entry when no ACT palette is selected explicitly.
- Builds a power-of-two DXT1 terrain atlas with a stock-style mip chain, generated per tile to avoid cross-tile mip bleeding.
- Converts locally supplied sky, cloud, `[Stars]`, and `[StarList]` textures and emits matching Redux materials while leaving stock-referenced textures unshadowed.
- Uses additive blending for `[Stars]` billboards and alpha blending for `[StarList]` content.

## Terrain Material Correction

- Emits a neutral 50% detail/specular texture for converted legacy terrain.
- Binds that neutral texture as both `DetailMap` and `SpecularMap`, avoiding the over-bright near-field result caused by the white defaults in `BZTerrainBase`.

## Validation

The legacy conversion path was validated end-to-end against the BZ 1.5 `earth` map: 38 source tiles were converted into a 2048x2048 DXT1 atlas with seven mip levels, correct transition orientation, required terrain/material bindings, and expected sky material handling. The existing test suite passed with 56 tests at the time of the conversion fix.

## Downloads

- `world-builder-windows.exe` — Windows standalone GUI build
- `world-builder-linux` — Linux standalone GUI build
- `world-builder-macos.zip` — complete macOS application bundle
