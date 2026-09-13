# Legacy Map Port CLI

WorldBuilder includes a console entry point for one-shot Battlezone 1.x to Battlezone 98 Redux map ports.

## Convert and validate

Extract the old map archive first, then run:

```powershell
.\world-builder-cli.exe legacy-port "<legacy-map-folder>" "<redux-output-folder>"
```

For a folder containing exactly one BZN, the atlas/material prefix defaults to the BZN stem. Override it with `--prefix` when needed. The palette referenced by the TRN is resolved automatically from the map or the embedded stock ACT set; `--palette` is available as a manual override.

The command runs the same Legacy Atlas, HGT conversion, and package finalizer used by the GUI, then runs launchability preflight. Exit code `0` means the package passed launch-critical checks. Exit code `2` means conversion completed but preflight found blocking errors.

The output includes the converted HG2, complete TRN, Redux INI, MAT/LGT companions, atlas/CSV/material assets, converted custom sky assets, resolved ACT palette, support files, optional preview PNG, `legacy_port_report.txt`, and `legacy_port_report.json`.

Legacy `.MAP` files are conversion inputs only and are not copied into the Redux launch folder. Terrain MAPs are packed into the generated atlas. Custom sky/cloud/star MAPs are converted to PNG/DDS plus Ogre material files. TRN `.MAP` tokens are retained because Redux resolves them as material names; the original indexed `.MAP` bytes are not required at runtime.

## Validate an existing output

```powershell
.\world-builder-cli.exe validate-port "<legacy-map-folder>" "<redux-output-folder>"
```

Use `--no-prepare` for validation without emitting the resolved ACT or preview helper files.

## Preflight checks

The validator checks BZN/INI presence, TRN geometry, HG2 dimensions, MAT size/material range, classic and Redux LGT layouts, the atlas material/CSV/texture chain, custom runtime dependencies, generated material-name case, and palette resolution. Stock/external dependencies not bundled with the map are reported as warnings rather than fabricated.
