# Battlezone98Redux World Builder v1.0.11

## Summary
v1.0.11 turns the Legacy Atlas workflow into a substantially more complete Battlezone 1.x -> Battlezone 98 Redux mission porter, adds deterministic stock-palette recovery, and adds a launchability preflight plus console CLI for immediate testing.

## Launchable Legacy Mission Packages
- Builds complete same-stem Redux TRN files instead of leaving `TRN_Entries.txt` for manual pasting.
- Preserves authored TRN world/size/origin/fog/sky/cloud/star/weather settings while replacing legacy texture bindings with the generated Redux atlas.
- Classifies BZN mission types (`MultSTMission`, `MultDMMission`, `LuaMission`, `Inst4XMission`, `EmptyMission`) and generates the corresponding Redux map INI.
- Recovers legacy display name/player capacity from MAD/DES/TXT metadata when available.
- Copies mission/runtime companions such as BZN, MAT, LGT, Lua/AIP/ODF/audio/custom assets while excluding obsolete executables and atlas-packed terrain MAP mip files.

## Legacy HGT -> HG2
- Keeps the Redux-equivalent `-nohgtsmoothing` HGT -> HG2 path integrated into the one-click Legacy Atlas workflow.
- Uses recovered 128 -> 256 triangle interpolation without the legacy 3x3 smoothing pass.

## Embedded Stock ACT Palettes
- Bundles all 33 supplied stock Battlezone ACT palettes directly into WorldBuilder.
- Palette resolution order: explicit user override -> map-bundled matching ACT -> embedded stock ACT named by TRN -> Moon only when the TRN declares no palette.
- Refuses mixed or unknown declared palettes instead of silently decoding indexed MAPs with the wrong colors.
- Emits the resolved ACT into the final output package.

## Launchability Preflight
After package finalization, WorldBuilder now validates the result before reporting `READY TO LAUNCH`:
- BZN + Redux INI presence.
- TRN Width/Depth geometry.
- HG2 zone count and Redux 256-sample-per-zone resolution.
- Exact MAT size and terrain material ID range.
- Legacy bordered 128-per-zone and Redux bordered 256-per-zone LGT layouts.
- `[Atlases] MaterialName` -> material -> CSV -> diffuse atlas texture chain.
- Custom runtime asset references and generated material-name case.
- Stock/external references are surfaced as warnings instead of being fabricated.

The output receives both `legacy_port_report.txt` and `legacy_port_report.json`. Same-stem legacy BMP previews are also converted to PNG when present.

## Command-Line Porting
A new Windows console executable is included:

```powershell
.\world-builder-cli.exe legacy-port "<legacy-map-folder>" "<redux-output-folder>"
```

The CLI drives the same Legacy Atlas/HGT/package implementation as the GUI and exits with code 0 only when launchability preflight passes. Existing output can be checked with:

```powershell
.\world-builder-cli.exe validate-port "<legacy-map-folder>" "<redux-output-folder>"
```

## Validation
- Full Windows, Linux, and macOS CI matrix passes on Python 3.10 and 3.11.
- Added regression coverage for embedded palette resolution and legacy terrain-MAP filtering.
- Release workflow now packages the Windows CLI alongside the normal GUI build.

## Downloads
- `world-builder-windows.exe`
- `world-builder-cli.exe`
- `world-builder-linux`
- `world-builder-macos.zip`
