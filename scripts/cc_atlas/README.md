# CC atlas builder — Combat Commander terrain art into Redux terrain atlases

Batch version of what the **Custom Atlas Creator** tab does interactively: take a
set of source textures, cut the solids and the cap/diagonal transition tiles,
pack them into one square atlas per channel, and write the `.csv` of UV rects,
the `.material`, and the `[TextureType]` blocks a `.trn` needs.

Two things it adds over the tab.

**It packs tight.** The hand-built ISDF Chronicles atlases are 8×8 grids holding
25–32 tiles — 39–50% of the cells carry art and the rest is black, because the
layout was drawn in an image editor and the CSV written to match it. Here the
grid is `ceil(sqrt(tiles))` and every spare cell is filled with a tile worth
having, so atlas area buys texels rather than padding. The arithmetic is kind:
*n* blend types produce exactly *n*² tiles (n solids, plus a cap and a diagonal
per unordered pair), so a world whose types all blend comes out an exactly full
*n* × *n* grid.

**It composites all four channels through one shared mask.** Normal, specular
and emissive come from the authored `_n` / `_s` / `_e` maps rather than being
derived from the finished diffuse, so a transition tile's normal describes the
surface instead of describing the diffuse's luminance.

## Files

| | |
|---|---|
| `worlds2.py` | every world: TextureType → source texture, which types blend, unused art |
| `build2.py` | the builder — planning, masking, mip chain, DDS/CSV/material output |
| `runall.py` | build several worlds in parallel, resumable |
| `prefetch.py` | mirror the source art locally first (see *Drive*, below) |
| `make_trn.py` | `[TextureType]` blocks, and a complete `.trn` for a brand-new world |
| `check_all.py` | seam contract, header/mip agreement, CSV shape, zero-file check |
| `verify_atlas.py` | the seam contract on its own, against the decoded DXT1 |
| `stage.py` | copy to a deliverable folder and md5 both sides |
| `table.py`, `compare_old_new.py`, `make_testmap.py` | reporting and in-game test carrier |
| `bc1.py`, `ddswrite.py`, `masks.py`, `build_world.py` | encoder, DDS writer, masks, shared helpers |

## Running it

```
set CC_ROOT=...\CombatCommanderSourceMaterialModsv2
set CC_MOD_DIR=...\Redux Maps\ISDF Chronicles
python prefetch.py
python runall.py out
python make_trn.py out
python check_all.py out
```

`CC_WORKERS` sets the parallelism (default 2). `CC_OLD_ATLASES` and
`REDUX_ADDON` only matter to the reporting and test-map scripts.

## Things that cost a day each

**The tile size is a property of the `.trn` key, not the filename.** Stock sets
make the two agree (`SolidA0 = ac00sA0.map`), but an author naming their own
tiles is under no obligation to.

**A transition in slot B has to blend the *B* solids of its two types**, because
that is the pair the engine puts either side of it when it picks slot B for a
cell. Blending the A art into a B cap fails the seam classifier outright.

**Read the source art from local disk.** With the CC tree on Google Drive, seven
encoder processes sat at 16% CPU while GoogleDriveFS burned 820 seconds
streaming 2048-square TGAs on demand. `prefetch.py` pulls each file once, in
parallel, and writes a tile-sized PNG into a local mirror that keeps the tree's
relative paths — so `load_source` finds it with nothing else to change.

**Validate output after a crash, not just after a write.** A host lock leaves
correctly-sized, all-NUL files: NTFS flushed the metadata and not the data. The
tell is that `build_report.json` is written last, so a world whose report parses
is a world that landed; `check_all.py` looks for NUL runs directly.

**A repacked atlas is not a drop-in for its own DDS.** Every UV rect changes when
the grid does, so the `.csv` must be copied with the `.dds`. Shipping the atlas
alone puts every tile in the wrong place.
