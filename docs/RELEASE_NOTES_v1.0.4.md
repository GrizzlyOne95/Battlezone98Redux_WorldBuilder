# Battlezone98Redux World Builder v1.0.4

## Summary

This maintenance release packages the current World Builder code after v1.0.3 and fixes the cross-platform release process, especially the broken macOS download from the previous release.

## Changed

- Includes the latest `world_builder.py` behavior changes currently on `main`.
- Refreshes the README/documentation for the current tool workflow.
- Updates GitHub Actions packaging to use current checkout/setup/upload actions.
- Windows releases are packaged as a standalone GUI executable.
- Linux releases remain a standalone executable.

## Fixed

- Fixes macOS release packaging. The old workflow uploaded only a tiny shell wrapper while leaving the actual `.app` bundle behind on the runner. v1.0.4 packages the complete `world_builder.app` bundle as `world-builder-macos.zip`.
- Adds minimum-size validation for all three platform assets so a tiny placeholder or incomplete package cannot be published silently.
- Release publication now waits for every platform build to succeed before creating the GitHub Release.

## Downloads

- `world-builder-windows.exe` — Windows standalone build
- `world-builder-linux` — Linux standalone build
- `world-builder-macos.zip` — complete macOS application bundle

## Installation

Download the asset for your platform from this release. On macOS, extract the ZIP and launch `world_builder.app`.
