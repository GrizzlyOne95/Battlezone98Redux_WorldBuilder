# Battlezone98Redux World Builder v1.0.8

## Summary

v1.0.8 adds native binary BZN support to the Mission Visualizer, removing the previous requirement to save missions as ASCII before loading their layout.

## Mission Visualizer

- Adds support for normal Battlezone 98 Redux / BZ1 hybrid BZN files that switch from an ASCII header to binary records through `binarySave`.
- Reads binary `TerrainName` so companion TRN and HG2 files can still be resolved automatically.
- Recovers GameObject visualization data from the stable BZ1 descriptor surface, including ODF/PrjID, sequence number, world position, team, and label.
- Recovers Redux/BZ1 AI paths, including path labels, point lists, and path type.
- Preserves the existing ASCII BZN parser path unchanged.
- Tolerates the known BZ1 binary field-type high-byte garbage quirk by using the low-byte type enumeration.
- Fails closed when declared object counts or binary structures cannot be recovered safely instead of silently plotting guessed data.

## Validation

The binary layout was cross-checked against `GrizzlyOne95/BZNTools`, including its BZN stream reader, Battlezone file loader, EntityDescriptor layout, and AiPath serialization.

Regression coverage includes binary terrain-name extraction, GameObject descriptors, AI paths, malformed object-count rejection, upper-byte type compatibility, and the existing HG2/TRN coordinate behavior.

## Downloads

- `world-builder-windows.exe` — Windows standalone GUI build
- `world-builder-linux` — Linux standalone GUI build
- `world-builder-macos.zip` — complete macOS application bundle
