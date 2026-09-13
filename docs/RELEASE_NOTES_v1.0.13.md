# Battlezone98Redux World Builder v1.0.13

## Legacy MAP files are conversion inputs only

v1.0.13 corrects the final Redux package layout for legacy ports.

Legacy `.MAP` files are no longer copied into the Redux launch folder at all.

This applies to:
- terrain tile MAPs and their mip variants
- custom sky MAPs
- cloud MAPs
- star/planet MAPs
- other legacy indexed MAP assets used as conversion sources

WorldBuilder still reads those legacy MAP files from the source package while porting. Terrain MAPs are packed into the generated Redux atlas, while custom sky/cloud/star MAPs are converted to modern PNG/DDS textures plus Ogre `.material` files.

The `.MAP` strings retained in the generated TRN are Redux material lookup names. They do not require the original legacy MAP byte files to ship in the final map package.

The generated material name continues to preserve the exact spelling/case authored in the TRN, including packages where the TRN says e.g. `blusky.map` but the physical legacy source file is `BLUSKY.MAP`.

## Validation

Added regression coverage proving that terrain, sky, and arbitrary legacy `.MAP` files are all excluded from the runtime support-file copy while launch-time companions such as BZN and WAV remain included.

The change passes the full Windows, Linux, and macOS CI matrix on Python 3.10 and 3.11.

## Downloads
- `world-builder-windows.exe`
- `world-builder-cli.exe`
- `world-builder-linux`
- `world-builder-macos.zip`
