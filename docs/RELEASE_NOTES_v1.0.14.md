# Battlezone98Redux World Builder v1.0.14

## Summary
v1.0.14 adds true batch legacy mission porting to both the CLI and GUI, building on the v1.0.13 one-stop Battlezone 1.x -> Battlezone 98 Redux conversion and validation workflow.

## Batch Legacy Mission Porting
Legacy map collections can now be organized as one mission package per immediate subfolder and converted in one run.

Example source layout:

```text
C:\BZ_Legacy_Maps\
├─ Legends\
├─ Scrapland\
├─ CanyonWar\
└─ ...
```

Each eligible child folder is converted into its own same-name Redux output folder. A child folder is eligible when it directly contains at least one BZN mission.

Batch processing deliberately scans immediate subfolders only. This keeps unrelated palettes, TRNs, MAP conversion sources, mission assets, and metadata isolated from each other.

## CLI
New command:

```powershell
.\world-builder-cli.exe legacy-port-batch "C:\BZ_Legacy_Maps" "C:\BZ_Redux_Maps"
```

Behavior:
- processes each immediate mission subfolder independently
- resolves each mission's palette independently by default
- derives the atlas/material prefix from the sole BZN stem when possible
- creates one same-name output folder per source mission folder
- continues to later missions after a conversion or preflight failure
- runs the same HGT/HG2, atlas, TRN, INI, asset, material, and launchability-preflight path as single-map conversion
- returns exit code `0` only when every discovered mission is READY TO LAUNCH
- returns exit code `2` when the batch completes but one or more missions are NOT READY or ERROR

A manual `--palette` option is available when intentionally applying the same ACT override to every mission in the batch. Automatic per-map palette resolution remains the recommended default.

## GUI
The Legacy Atlas page now includes **Batch Port Mission Folders** with:
- source parent-folder picker
- Redux output parent-folder picker
- mission-folder scan/count
- optional shared manual ACT override
- `BATCH PORT SUBFOLDERS` action
- final READY/failed summary

The GUI batch workflow reuses the existing single-map Legacy Atlas worker rather than maintaining a separate conversion implementation.

## Batch Reports
The batch output root receives:

```text
legacy_batch_report.txt
legacy_batch_report.json
```

Each processed map is classified as `READY`, `NOT_READY`, or `ERROR`, with its output directory, prefix, warning/error counts, individual preflight report path, and diagnostic message.

Each mission output also retains its normal per-map:

```text
legacy_port_report.txt
legacy_port_report.json
```

## Fault Isolation
A malformed or incomplete mission package no longer aborts a large collection conversion. The batch engine records the failure and continues with the remaining mission folders.

## Validation
- full Windows/Linux/macOS CI matrix passes on Python 3.10 and 3.11
- regression coverage for immediate-subfolder discovery
- regression coverage for single-BZN prefix derivation
- regression coverage for continue-on-failure behavior
- parent-level TXT/JSON batch reports
- source/output root safety check
- CLI/GUI batch modules included in release compile/import verification

## Downloads
- `world-builder-windows.exe`
- `world-builder-cli.exe`
- `world-builder-linux`
- `world-builder-macos.zip`
