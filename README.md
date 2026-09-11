# Battlezone98Redux_WorldBuilder
A powerful world building tool that auto creates custom atlases, material files, TRN entries, cubemaps, HG2/HGT conversion, and more

## Stock Map Creator
Auto generates TRN, HG2, and MAT files based on default worlds without needing to use MakeTRN. Implements some rarely used paramters for tweaking. 

<img width="1402" height="982" alt="python_el54uNiI0s" src="https://github.com/user-attachments/assets/057925a0-8737-4771-8830-6548a5c439d9" />


## Custom Atlas Creator
Creating a custom atlas with manually painted transitions can be very time consuming. This tool lets you point to a folder of solid textures, and it will arrange them on a grid, generate cap/diagonal transitions with many adjustment paramters, and exports with all the correct entries for TRN, CSV, Material, etc. 

<img width="1402" height="982" alt="python_0sHojush7m" src="https://github.com/user-attachments/assets/e8114ca7-ae38-49b0-99dc-30fe433b2714" />

## Legacy Atlas Creator
Ports custom worlds from 1.5 format into Redux. Auto converts the .MAP files into an atlas, and exports the proper TRN, CSV, Material.

<img width="1402" height="982" alt="python_TDaQIDixe7" src="https://github.com/user-attachments/assets/0ad9a060-8804-4e1e-b81d-e146e3d4d908" />

## Heightmap Converter
Ports HGT or HG2 to PNG, or PNG back to HGT/HG2. Experimental World Machine implementation. 

<img width="1402" height="982" alt="python_KBNkOhWxwZ" src="https://github.com/user-attachments/assets/5acc659f-bc2e-4d3e-87c5-1edeb8a86576" />


## Skybox Tools
You just need a single HDRI/Equirectangular Projected Skybox image and this will convert it into cubemap faces, and generate all the material/DDS/TRN entries you need to make some awesome BZR skies.

<img width="1402" height="982" alt="python_Upj2ePSle0" src="https://github.com/user-attachments/assets/ad05eb5a-20c2-4604-9779-5bb8057dd7cc" />


## Mission Visualizer
Experimental mission layout summarizer that loads the heightmap and BZN.

<img width="1402" height="982" alt="python_RPojjiNh4q" src="https://github.com/user-attachments/assets/4628aece-bd05-43c3-ae00-51fc11ad95cc" />


## Auto-Painter
Lets you define painting rules for custom painting, and manually writes the MAT file. Full replacement for MakeTRN /p.

The painter core is reverse-engineered from the historical MakeTRN executable and shared by both the GUI and the open-source `bzpaint.py` command-line frontend. It preserves MakeTRN's layer ordering, elevation/slope sampling, cap/diagonal synthesis, MAT layout, and MSVCR120 variant logic while adding deterministic output and diagnostics.

Legacy-style usage:

```powershell
python bzpaint.py mapname.trn /p=moon.ini
```

`bzpaint.py` automatically loads `mapname.hg2` and writes `mapname.mat`. If `/p=` is omitted it uses the actual built-in MakeTRN defaults recovered from the executable.

Modern options can be mixed with the legacy syntax:

```powershell
python bzpaint.py mapname.trn /p=moon.ini --seed 1 --dry-run
python bzpaint.py mapname.trn --params moon.ini --output custom.mat --json
python bzpaint.py mapname.trn /p=moon.ini /e=0
```

Useful options:

- `--seed N` selects the deterministic MSVCR120-compatible texture-variant seed. The historical executable used `srand(clock())`; WorldBuilder defaults to `1` for reproducible builds.
- `--dry-run` performs the complete paint and transition validation without writing a MAT.
- `--json` prints machine-readable statistics and diagnostics.
- `--output FILE` chooses a MAT path instead of replacing the TRN suffix with `.mat`.
- `/e=N` or `--empty-elevation N` controls the legacy out-of-bounds EmptyElevation value.

See [`docs/MAT_FORMAT_VALIDATION.md`](docs/MAT_FORMAT_VALIDATION.md) for the recovered format and MakeTRN behavior.

<img width="1402" height="982" alt="python_1O4aYb26T2" src="https://github.com/user-attachments/assets/d91b2377-129a-46c3-9942-a8695927f0f4" />








