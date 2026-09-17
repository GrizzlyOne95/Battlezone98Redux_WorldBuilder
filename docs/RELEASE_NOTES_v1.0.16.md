# Battlezone98Redux World Builder v1.0.16

## Summary
v1.0.16 applies the canonical World Builder branding throughout the Windows application. The packaged executables, taskbar, Alt-Tab, and Tk window now all use the icon derived from `branding/repo_icon.svg`. There are no terrain-toolchain changes.

## Highlights
- Rebuild `wb.ico` from the canonical path-based `branding/repo_icon.svg` with a path-capable generator (previous generator assumed the old text/circle artwork).
- Brand the compiled Windows executables (`--icon=wb.ico` for both the GUI and CLI builds).
- Apply the bundled icon to the Tk root window at runtime with frozen (`sys._MEIPASS`) and source-tree resource lookup.
- Set a stable Windows AppUserModelID (`GrizzlyOne95.Battlezone98Redux.WorldBuilder`) so taskbar grouping and icon behavior are reliable.
- Bundle the multi-resolution ICO (16x16 through 256x256) plus PNG in the PyInstaller build with a runtime icon hook.

## Validation
- `python -m unittest discover -s tests` passes (98 tests).
- Release workflow validates frozen-asset sizes and `imageio` distribution metadata.
