# Battlezone98Redux World Builder v1.0.12

## Summary
v1.0.12 is the finalized legacy-port release. It contains the full v1.0.11 legacy package, embedded palette, preflight, and CLI work plus a compatibility fix found while validating the real Legends map.

## Exact TRN Material Lookup Names
Classic maps can reference a custom MAP with different filename casing than the physical file, for example:

```ini
SkyTexture=blusky.map
```

while the package contains `BLUSKY.MAP`.

The legacy converter previously generated the Ogre material name from the physical filename. The finalizer now normalizes generated custom sky/cloud/star material declarations back to the exact spelling authored in the TRN before launchability preflight runs. This avoids relying on case-insensitive resource lookup and keeps ports deterministic across Windows/Linux environments.

## Included from v1.0.11
- Complete Redux TRN generation instead of manual `TRN_Entries.txt` pasting.
- BZN mission-type classification and Redux INI generation.
- Legacy metadata recovery for display name/player capacity.
- Redux-equivalent no-smoothing HGT -> HG2 conversion.
- All 33 supplied stock ACT palettes embedded with deterministic TRN palette resolution and manual override support.
- Resolved ACT emission into the output package.
- MAT and classic/Redux LGT validation.
- Atlas/material/CSV/texture-chain validation.
- Custom runtime dependency audit.
- Legacy preview BMP -> PNG conversion.
- `legacy_port_report.txt` and JSON launchability reports.
- Terrain MAP mip files omitted after packing into the Redux atlas.
- Windows `world-builder-cli.exe` for copy/paste one-shot ports and validation.

## CLI

```powershell
.\world-builder-cli.exe legacy-port "<legacy-map-folder>" "<redux-output-folder>"
```

Validate an existing port with:

```powershell
.\world-builder-cli.exe validate-port "<legacy-map-folder>" "<redux-output-folder>"
```

## Validation
The material-name normalization change passed the full Windows/Linux/macOS CI matrix on Python 3.10 and 3.11.

## Downloads
- `world-builder-windows.exe`
- `world-builder-cli.exe`
- `world-builder-linux`
- `world-builder-macos.zip`
