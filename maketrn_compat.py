from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass

import numpy as np


METERS_PER_HG2_SAMPLE = 5
HG2_SAMPLES_PER_ZONE = 256
HGT_SAMPLES_PER_ZONE = 128
METERS_PER_ZONE = METERS_PER_HG2_SAMPLE * HG2_SAMPLES_PER_ZONE
MAKE_TRN_EMPTY_ELEVATION_MAX = 4094
MSVCR_CLOCKS_PER_SEC = 1000


@dataclass(frozen=True)
class StockGeometry:
    width_meters: int
    depth_meters: int
    zones_x: int
    zones_z: int


def normalize_make_trn_dimension(meters: int) -> int:
    """Reproduce MakeTRN's /w and /h integer normalization.

    The binary first truncates meters to 5 m samples, then rounds the sample
    count upward to a 256-sample boundary. This is subtly different from a
    straight ceil(meters / 1280) for values that are not multiples of 5.
    Values below 5 m quantize to zero samples in MakeTRN; WorldBuilder rejects
    them instead of attempting to create a zero-sized terrain.
    """
    meters = int(meters)
    if meters <= 0:
        raise ValueError("Terrain dimensions must be positive")
    samples = math.trunc(meters / METERS_PER_HG2_SAMPLE)
    samples = (samples + (HG2_SAMPLES_PER_ZONE - 1)) & ~(HG2_SAMPLES_PER_ZONE - 1)
    if samples <= 0:
        raise ValueError("Terrain dimensions must be at least 5 meters")
    return samples * METERS_PER_HG2_SAMPLE


def make_stock_geometry(width_meters: int, depth_meters: int) -> StockGeometry:
    width = normalize_make_trn_dimension(width_meters)
    depth = normalize_make_trn_dimension(depth_meters)
    return StockGeometry(
        width_meters=width,
        depth_meters=depth,
        zones_x=width // METERS_PER_ZONE,
        zones_z=depth // METERS_PER_ZONE,
    )


def validate_empty_elevation(value: int) -> int:
    """Validate the range actually accepted by MakeTRN 2.1.2's /e parser."""
    value = int(value)
    if not 0 <= value <= MAKE_TRN_EMPTY_ELEVATION_MAX:
        raise ValueError(
            f"Empty elevation must be 0..{MAKE_TRN_EMPTY_ELEVATION_MAX} "
            "for MakeTRN 2.1.2 compatibility"
        )
    return value


def make_trn_runtime_seed() -> int:
    """Approximate MSVCR120 clock() for legacy srand(clock()) behavior.

    Visual C++ clock() uses CLOCKS_PER_SEC=1000. Python process_time() is the
    closest cross-platform source because both measure process CPU time rather
    than wall-clock time. Only the low 32 bits matter to the emulated PRNG.
    """
    return int(time.process_time() * MSVCR_CLOCKS_PER_SEC) & 0xFFFFFFFF


def stock_trn_height(empty_elevation: int) -> float:
    """TRN Height written by MakeTRN's blank-create path."""
    return validate_empty_elevation(empty_elevation) * 0.1


def unpack_hgt_zones(payload: bytes, zones_x: int, zones_z: int) -> np.ndarray:
    """Decode a legacy HGT payload into a north-unmodified raster.

    HGT has no header. It stores 128x128 unsigned-16 blocks in zone-major
    order. Redux/MakeTRN use the low 12 bits of every source sample when
    upgrading the terrain to the 256-sample-per-zone HG2 grid.
    """
    zones_x = int(zones_x)
    zones_z = int(zones_z)
    if zones_x <= 0 or zones_z <= 0:
        raise ValueError("HGT zone dimensions must be positive")
    zone_samples = HGT_SAMPLES_PER_ZONE * HGT_SAMPLES_PER_ZONE
    expected = zones_x * zones_z * zone_samples * 2
    if len(payload) != expected:
        raise ValueError(f"HGT size mismatch: expected {expected} bytes, found {len(payload)}")

    raw = np.frombuffer(payload, dtype="<u2") & 0x0FFF
    out = np.empty(
        (zones_z * HGT_SAMPLES_PER_ZONE, zones_x * HGT_SAMPLES_PER_ZONE),
        dtype=np.uint16,
    )
    cursor = 0
    for zone_z in range(zones_z):
        for zone_x in range(zones_x):
            zone = raw[cursor : cursor + zone_samples].reshape(
                (HGT_SAMPLES_PER_ZONE, HGT_SAMPLES_PER_ZONE)
            )
            z0 = zone_z * HGT_SAMPLES_PER_ZONE
            x0 = zone_x * HGT_SAMPLES_PER_ZONE
            out[z0 : z0 + HGT_SAMPLES_PER_ZONE, x0 : x0 + HGT_SAMPLES_PER_ZONE] = zone
            cursor += zone_samples
    return out


def interpolate_hgt_to_hg2(legacy: np.ndarray) -> np.ndarray:
    """Upgrade the 128-sample HGT grid to Redux's 256-sample HG2 grid.

    This is the recovered Battlezone triangle interpolation step only. Each
    source quad is split along the A->C diagonal and sampled at half-sample
    positions. Right/bottom neighbors clamp at the far edge. No smoothing,
    filtering, resampling kernel, or height renormalization is applied.

    This is the terrain shape produced by Redux's legacy HGT upgrade path when
    the `nohgtsmoothing` launch option disables the subsequent smoothing pass.
    """
    src = np.asarray(legacy, dtype=np.uint16) & 0x0FFF
    if src.ndim != 2 or src.shape[0] == 0 or src.shape[1] == 0:
        raise ValueError("HGT raster must be a non-empty 2D array")

    src32 = src.astype(np.uint32)
    right = np.empty_like(src32)
    right[:, :-1] = src32[:, 1:]
    right[:, -1] = src32[:, -1]
    down = np.empty_like(src32)
    down[:-1, :] = src32[1:, :]
    down[-1, :] = src32[-1, :]
    diagonal = np.empty_like(src32)
    diagonal[:-1, :-1] = src32[1:, 1:]
    diagonal[-1, :-1] = src32[-1, 1:]
    diagonal[:-1, -1] = src32[1:, -1]
    diagonal[-1, -1] = src32[-1, -1]

    interpolated = np.empty((src.shape[0] * 2, src.shape[1] * 2), dtype=np.uint16)
    interpolated[0::2, 0::2] = src
    interpolated[0::2, 1::2] = ((src32 + right) // 2).astype(np.uint16)
    interpolated[1::2, 0::2] = ((src32 + down) // 2).astype(np.uint16)
    interpolated[1::2, 1::2] = ((src32 + diagonal) // 2).astype(np.uint16)
    return interpolated


def smooth_make_trn_hg2(raster: np.ndarray) -> np.ndarray:
    """Reproduce the legacy post-interpolation 3x3 smoothing pass.

    Function 0x40180b copies the interpolated Redux raster, then replaces every
    sample with the rounded mean of the in-bounds 3x3 neighborhood. Border
    samples therefore use 4 or 6 values rather than replicated edge pixels.
    The integer expression is `(2 * sum + count) / (2 * count)`, i.e. positive
    half-up rounding rather than truncation.
    """
    src = np.asarray(raster, dtype=np.uint16)
    if src.ndim != 2 or src.shape[0] == 0 or src.shape[1] == 0:
        raise ValueError("HG2 raster must be a non-empty 2D array")

    height, width = src.shape
    sums = np.zeros((height, width), dtype=np.uint32)
    counts = np.zeros((height, width), dtype=np.uint16)
    src32 = src.astype(np.uint32)

    for dz in (-1, 0, 1):
        src_z0 = max(0, -dz)
        src_z1 = min(height, height - dz)
        dst_z0 = src_z0 + dz
        dst_z1 = src_z1 + dz
        for dx in (-1, 0, 1):
            src_x0 = max(0, -dx)
            src_x1 = min(width, width - dx)
            dst_x0 = src_x0 + dx
            dst_x1 = src_x1 + dx
            sums[dst_z0:dst_z1, dst_x0:dst_x1] += src32[src_z0:src_z1, src_x0:src_x1]
            counts[dst_z0:dst_z1, dst_x0:dst_x1] += 1

    rounded = (2 * sums + counts.astype(np.uint32)) // (2 * counts.astype(np.uint32))
    return rounded.astype(np.uint16)


def upsample_hgt_to_hg2(legacy: np.ndarray) -> np.ndarray:
    """Reproduce MakeTRN/Redux's normal HGT upgrade including smoothing."""
    return smooth_make_trn_hg2(interpolate_hgt_to_hg2(legacy))


def read_hgt_as_hg2(
    path: os.PathLike | str,
    zones_x: int,
    zones_z: int,
    *,
    smooth: bool = True,
) -> np.ndarray:
    """Read legacy HGT and return a Redux-resolution height raster.

    `smooth=True` preserves the existing MakeTRN-compatible behavior.
    `smooth=False` matches the Redux legacy-upgrade path with `nohgtsmoothing`.
    """
    with open(path, "rb") as stream:
        legacy = unpack_hgt_zones(stream.read(), zones_x, zones_z)
    interpolated = interpolate_hgt_to_hg2(legacy)
    return smooth_make_trn_hg2(interpolated) if smooth else interpolated


def read_hgt_as_hg2_no_smoothing(
    path: os.PathLike | str,
    zones_x: int,
    zones_z: int,
) -> np.ndarray:
    """Explicit helper for Redux-equivalent `nohgtsmoothing` terrain upgrades."""
    return read_hgt_as_hg2(path, zones_x, zones_z, smooth=False)


def convert_hgt_to_hg2_no_smoothing(
    hgt_path: os.PathLike | str,
    hg2_path: os.PathLike | str,
    zones_x: int,
    zones_z: int,
) -> np.ndarray:
    """Convert an authored 1.5 HGT to Redux HG2 without the smoothing pass."""
    from hg2_codec import DEFAULT_ZONE_BITS, write_hg2

    heights = read_hgt_as_hg2_no_smoothing(hgt_path, zones_x, zones_z)
    write_hg2(
        hg2_path,
        heights,
        zones_x=int(zones_x),
        zones_z=int(zones_z),
        zone_bits=DEFAULT_ZONE_BITS,
    )
    return heights


def _install_world_builder_legacy_hgt_ui_patch() -> None:
    """Attach the converter to the existing Legacy Atlas page when available.

    `world_builder.py` imports this module after `world_builder_core`, before the
    application instance is constructed. Wrapping the base setup method keeps
    the feature isolated here while preserving the existing Legacy Atlas UI.
    Unit-test imports do not load `world_builder_core`, so they remain headless.
    """
    core = sys.modules.get("world_builder_core")
    if core is None:
        return
    base = getattr(core, "BZ98TRNArchitect", None)
    if base is None or getattr(base, "_legacy_hgt_converter_installed", False):
        return

    original_setup = base.setup_legacy_tab

    def setup_legacy_tab_with_hgt(self):
        original_setup(self)

        self.legacy_hgt_path = core.tk.StringVar()
        self.legacy_hgt_info = core.tk.StringVar(
            value="Select an authored BZ 1.5 .HGT. Companion .TRN dimensions are used automatically."
        )

        frame = core.ttk.LabelFrame(
            self.tab_legacy,
            text=" Legacy Terrain Upgrade (.HGT -> .HG2, no smoothing) ",
            padding=10,
        )
        frame.pack(fill="x", padx=20, pady=(0, 10))

        row = core.ttk.Frame(frame)
        row.pack(fill="x")
        entry = core.ttk.Entry(row, textvariable=self.legacy_hgt_path)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_hgt():
            path = core.filedialog.askopenfilename(
                title="Select original Battlezone HGT",
                filetypes=[("Battlezone Height Terrain", "*.hgt"), ("All Files", "*.*")],
            )
            if not path:
                return
            self.legacy_hgt_path.set(path)
            trn_path = os.path.splitext(path)[0] + ".trn"
            trn = core.TRNParser.parse(trn_path)
            if trn.get("Width") and trn.get("Depth"):
                try:
                    zones_x = int(round(float(trn["Width"]) / METERS_PER_ZONE))
                    zones_z = int(round(float(trn["Depth"]) / METERS_PER_ZONE))
                    expected = zones_x * zones_z * HGT_SAMPLES_PER_ZONE * HGT_SAMPLES_PER_ZONE * 2
                    actual = os.path.getsize(path)
                    suffix = "" if actual == expected else f" | WARNING size {actual}, expected {expected}"
                    self.legacy_hgt_info.set(
                        f"{os.path.basename(trn_path)}: {zones_x}x{zones_z} zones -> "
                        f"{zones_x * HG2_SAMPLES_PER_ZONE}x{zones_z * HG2_SAMPLES_PER_ZONE} HG2{suffix}"
                    )
                except Exception as exc:
                    self.legacy_hgt_info.set(f"Could not validate companion TRN: {exc}")
            else:
                self.legacy_hgt_info.set("Companion .TRN with [Size] Width/Depth is required.")

        core.ttk.Button(row, text="Browse HGT", command=browse_hgt).pack(side="left")
        core.ttk.Label(
            frame,
            textvariable=self.legacy_hgt_info,
            foreground=core.BZ_CYAN,
            font=("Consolas", 9),
        ).pack(anchor="w", pady=(5, 5))
        core.ttk.Label(
            frame,
            text=(
                "Matches Redux legacy terrain upgrading with -nohgtsmoothing: "
                "12-bit HGT samples -> recovered 2x triangle interpolation -> HG2. "
                "No 3x3 smoothing, Gaussian filtering, or height renormalization."
            ),
            foreground="#888888",
            wraplength=1050,
        ).pack(anchor="w", pady=(0, 7))

        def convert_selected_hgt():
            hgt_path = self.legacy_hgt_path.get().strip()
            if not hgt_path or not os.path.isfile(hgt_path):
                core.messagebox.showerror("Legacy HGT", "Select a valid .HGT file first.")
                return
            trn_path = os.path.splitext(hgt_path)[0] + ".trn"
            trn = core.TRNParser.parse(trn_path)
            width = trn.get("Width")
            depth = trn.get("Depth")
            if not width or not depth:
                core.messagebox.showerror(
                    "Legacy HGT",
                    "A companion .TRN with [Size] Width and Depth is required to determine HGT zone dimensions.",
                )
                return
            zones_x_f = float(width) / METERS_PER_ZONE
            zones_z_f = float(depth) / METERS_PER_ZONE
            zones_x = int(round(zones_x_f))
            zones_z = int(round(zones_z_f))
            if (
                zones_x <= 0
                or zones_z <= 0
                or abs(zones_x_f - zones_x) > 1e-6
                or abs(zones_z_f - zones_z) > 1e-6
            ):
                core.messagebox.showerror(
                    "Legacy HGT",
                    "Companion TRN Width/Depth must be exact 1280 m terrain-zone multiples.",
                )
                return

            default_dir = self.legacy_out_dir.get().strip() or os.path.dirname(hgt_path)
            output = core.filedialog.asksaveasfilename(
                title="Save Redux HG2",
                initialdir=default_dir,
                initialfile=os.path.splitext(os.path.basename(hgt_path))[0] + ".hg2",
                defaultextension=".hg2",
                filetypes=[("Battlezone Redux Heightmap", "*.hg2")],
            )
            if not output:
                return
            try:
                heights = convert_hgt_to_hg2_no_smoothing(
                    hgt_path, output, zones_x, zones_z
                )
                self.log(
                    f"Legacy HGT -> HG2 (-nohgtsmoothing): {os.path.basename(hgt_path)} -> "
                    f"{os.path.basename(output)} | {zones_x}x{zones_z} zones | "
                    f"range {int(heights.min())}..{int(heights.max())}",
                    "success",
                )
                core.messagebox.showinfo(
                    "Legacy HGT Converted",
                    f"Saved {output}\n\n"
                    f"{zones_x}x{zones_z} zones, "
                    f"{heights.shape[1]}x{heights.shape[0]} HG2 samples.\n"
                    "Triangle interpolation only; smoothing was not applied.",
                )
            except Exception as exc:
                self.log(f"Legacy HGT conversion failed: {exc}", "error")
                core.messagebox.showerror("Legacy HGT", str(exc))

        self.btn_legacy_hgt_convert = core.ttk.Button(
            frame,
            text="CONVERT HGT -> HG2 (NO SMOOTHING)",
            command=convert_selected_hgt,
            style="Action.TButton",
        )
        self.btn_legacy_hgt_convert.pack(fill="x")

    base.setup_legacy_tab = setup_legacy_tab_with_hgt
    base._legacy_hgt_converter_installed = True


_install_world_builder_legacy_hgt_ui_patch()
