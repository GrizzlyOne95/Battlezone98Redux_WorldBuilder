# Battlezone98Redux World Builder v1.0.7

## Summary

v1.0.7 is a packaging hotfix for the standalone executables published in v1.0.6.

The v1.0.6 frozen builds included the `imageio` Python package but omitted its distribution metadata. `imageio` queries its installed version through `importlib.metadata` during import, so the standalone executable could terminate at startup with:

```text
importlib.metadata.PackageNotFoundError: No package metadata was found for imageio
```

The application source itself was unaffected.

## Fixed

- PyInstaller release builds now explicitly include `imageio` distribution metadata using `--copy-metadata imageio` on Windows, Linux, and macOS.
- Release builds now verify that the frozen payload actually contains `imageio` `.dist-info` metadata before artifacts can be uploaded.
- This prevents the startup crash seen in the v1.0.6 standalone binaries.

## Downloads

- `world-builder-windows.exe` — Windows standalone GUI build
- `world-builder-linux` — Linux standalone GUI build
- `world-builder-macos.zip` — complete macOS application bundle

## Note for v1.0.6 users

If your v1.0.6 standalone executable fails during startup with `PackageNotFoundError` for `imageio`, replace it with the corresponding v1.0.7 build.
