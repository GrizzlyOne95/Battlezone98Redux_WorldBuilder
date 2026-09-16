# Battlezone98Redux World Builder v1.0.15

## Summary
v1.0.15 expands World Builder's terrain and legacy-map toolchain with HG2 <-> Wavefront OBJ round-tripping, native 16-bit legacy MAP decoding, automatic map preview rendering, and new terrain-atlas rebuild utilities. It also improves release validation and gives the Windows builds canonical World Builder branding.

## HG2 Terrain OBJ Round-Trip
The Heightmap Converter now supports exporting Redux HG2 terrain to Wavefront OBJ and importing edited OBJ terrain back to HG2.

Highlights:
- dependency-free terrain OBJ codec
- preserves HG2 terrain dimensions and metadata needed for a reliable round-trip
- uses Redux world-grid coordinates rather than TerraZone's legacy fixed spacing assumptions
- validates vertex count, ordering, and grid shape on import
- hardened parsing for OBJ vertex records and malformed input
- expanded regression coverage for rectangular terrain, metadata, coordinates, and round-trip fidelity
- included in CI and release import/syntax verification

This provides a Blender-independent terrain mesh interchange path while still allowing OBJ files to be edited in Blender or other DCC tools when desired.

## Legacy 16-bit MAP Support
The Legacy Atlas workflow can now decode the two 16-bit Battlezone MAP formats already represented by the format enum:
- ARGB4444
- RGB565

Previously, non-indexed MAP data fell through to the 32-bit BGRA path, causing common community planet sets to fail or be silently skipped. Channel expansion now preserves the full 8-bit range, and cloud/star alpha-key handling correctly supports non-indexed source plates.

This is particularly important for legacy 1.4/1.5 community terrain sets that were not authored as 8-bit indexed MAP tiles.

## Automatic Map Preview Rendering
World Builder can now render map preview artwork directly from a Redux map's own data instead of requiring screenshots.

The preview renderer combines:
- MAT terrain-material assignments
- TRN atlas/tile mappings
- terrain atlas average colors
- HG2 relief shading

It can produce:
- the stock-style 108x89 in-game shell preview
- a larger square preview suitable for Workshop/catalog use

Relief is derived at preview resolution so terrain forms remain readable without introducing upsampled heightfield speckle.

## Terrain Atlas Rebuild Utilities
The repository now includes the `scripts/cc_atlas` terrain-atlas rebuild toolchain used for Combat Commander / ISDF Chronicles-style source art.

Capabilities include:
- batch rebuilding multiple world atlases
- dense/tight atlas packing instead of large black unused regions
- coordinated diffuse, normal, specular, and emissive compositing
- DXT1/BC1 output with mip chains
- transition verification and contact-sheet generation
- replacement TRN generation while preserving non-TextureType content and original line-ending behavior
- detail-map normalization against measured stock terrain behavior
- installation tooling with backups and hash verification
- support for alternate source roots such as Forgotten Enemies-derived Mercury art

These utilities are primarily repository/developer tooling rather than required runtime dependencies for the main GUI.

## Branding and Packaging
- Windows GUI and CLI builds now use the canonical World Builder application icon generated from the repository SVG source.
- Repository branding assets and icon-source documentation were added.
- Release-build checks now explicitly compile/import the terrain OBJ module.

## Validation
- latest main Build workflow passes before release
- terrain OBJ round-trip tests cover metadata, grid validation, coordinates, and fidelity
- map preview regression tests are included
- pytest is explicitly available to CI
- Linux, Windows, and macOS release packaging retain the existing executable-size and imageio metadata checks

## Downloads
- `world-builder-windows.exe`
- `world-builder-cli.exe`
- `world-builder-linux`
- `world-builder-macos.zip`
