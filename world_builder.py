from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageFilter, ImageTk

import world_builder_core as core
from world_builder_core import *
from hg2_codec import (
    DEFAULT_ZONE_BITS,
    hg2_to_png16_array,
    read_hg2,
    read_hg2_header,
    write_hg2,
)
from mat_codec import (
    PAINTER_MAX_ELEVATION_DM,
    generate_mat,
    parse_trn_painter,
    validate_paint_rules,
    write_mat,
)


_BaseArchitect = core.BZ98TRNArchitect


class BZ98TRNArchitect(_BaseArchitect):
    """World Builder with canonical Battlezone 98 Redux HG2 and MAT I/O."""

    def browse_hg2(self):
        path = core.filedialog.askopenfilename(
            filetypes=[("Heightmaps", "*.hg2 *.hgt *.png *.bmp")]
        )
        if not path:
            return

        self.hg2_path.set(path)
        if path.lower().endswith(".hg2"):
            try:
                header = read_hg2_header(path)
                self.hg2_target_zw.set(header.zones_x)
                self.hg2_target_zl.set(header.zones_z)
            except Exception as exc:
                core.messagebox.showerror("HG2 Error", str(exc))
                return
        elif path.lower().endswith(".hgt"):
            try:
                trn_path = os.path.splitext(path)[0] + ".trn"
                trn = core.TRNParser.parse(trn_path)
                if trn.get("Width") and trn.get("Depth"):
                    zw = int(round(trn["Width"] / 1280.0))
                    zl = int(round(trn["Depth"] / 1280.0))
                    if zw > 0 and zl > 0:
                        self.hg2_target_zw.set(zw)
                        self.hg2_target_zl.set(zl)
            except Exception:
                pass

        self.update_hg2_preview()

    def update_hg2_preview(self, *args):
        path = self.hg2_path.get()
        if not path or not os.path.exists(path):
            return
        if not path.lower().endswith(".hg2"):
            return super().update_hg2_preview(*args)

        try:
            _, heights = read_hg2(path)

            # Work in the same 16-bit interchange space used by PNG export so
            # brightness/contrast are consistent for HG2 and lossless PNG input.
            arr = hg2_to_png16_array(heights).astype(np.float32)
            arr *= self.hg2_brightness.get()
            mean = 32768.0
            arr = (arr - mean) * self.hg2_contrast.get() + mean

            temp_img = Image.fromarray(arr, mode="F")
            if self.hg2_smooth_val.get() > 0:
                temp_img = temp_img.filter(ImageFilter.GaussianBlur(self.hg2_smooth_val.get()))
            final_arr = np.array(temp_img)

            f_min, f_max = final_arr.min(), final_arr.max()
            if f_max > f_min:
                norm_arr = (final_arr - f_min) / (f_max - f_min)
            else:
                norm_arr = final_arr / 65535.0
            preview_8bit = Image.fromarray((np.clip(norm_arr, 0.0, 1.0) * 255).astype(np.uint8))

            cw = self.hg2_preview_canvas.winfo_width()
            ch = self.hg2_preview_canvas.winfo_height()
            if cw < 10:
                cw, ch = 600, 600
            preview_8bit.thumbnail((cw, ch), self.resample_method)
            self.hg2_tk_photo = ImageTk.PhotoImage(preview_8bit)
            self.hg2_preview_canvas.delete("all")
            self.hg2_preview_canvas.create_image(cw // 2, ch // 2, image=self.hg2_tk_photo)
        except Exception as exc:
            print(f"Preview Update Error: {exc}")

    def convert_hg2_to_png(self):
        path = self.hg2_path.get()
        if not path or not os.path.exists(path):
            return
        if not path.lower().endswith(".hg2"):
            return super().convert_hg2_to_png()

        self.btn_hg2_png.config(text="CONVERTING...", state="disabled")
        try:
            _, heights = read_hg2(path)
            out_path = os.path.splitext(path)[0] + "_edit.png"

            if self.hg2img_compat.get():
                # Preserve the existing HG2IMG compatibility representation.
                h = (heights & 0x0FFF).astype(np.uint16)
                h = np.flipud(h)
                g = (h >> 4).astype(np.uint8)
                if self.hg2img_precision.get():
                    r = (h & 0x0F).astype(np.uint8)
                else:
                    r = np.zeros_like(g, dtype=np.uint8)
                b = np.zeros_like(g, dtype=np.uint8)
                a = np.full_like(g, 255, dtype=np.uint8)
                out_img = Image.fromarray(np.dstack([r, g, b, a]), mode="RGBA")
                out_img.save(out_path)
                self.log(
                    f"Success: Converted (HG2IMG legacy) ({out_img.width}x{out_img.height})",
                    "success",
                )
            else:
                out_img = Image.fromarray(hg2_to_png16_array(heights), mode="I;16")
                out_img.save(out_path)
                self.log(
                    f"Success: Converted ({out_img.width}x{out_img.height})",
                    "success",
                )
        except Exception as exc:
            self.log(f"Error: Conversion failed: {exc}", "error")
        finally:
            self.root.after(
                0,
                lambda: self.btn_hg2_png.config(text="HG2 -> PNG", state="normal"),
            )

    def browse_mission_bg(self):
        path = core.filedialog.askopenfilename(
            filetypes=[("Map Image", "*.hg2 *.png *.bmp *.jpg")]
        )
        if not path:
            return

        try:
            if path.lower().endswith(".hg2"):
                _, heights = read_hg2(path)
                peak = max(int(heights.max()), 1)
                arr_norm = np.clip(
                    heights.astype(np.float32) / float(peak) * 255.0,
                    0,
                    255,
                ).astype(np.uint8)
                img = Image.fromarray(arr_norm)
            else:
                img = Image.open(path).convert("L")

            self.mission_bg_img = img
            self.redraw_mission_canvas()
        except Exception as exc:
            core.messagebox.showerror("Error", f"Failed to load map: {exc}")

    def _read_hgt_for_painter(self, path):
        zones_x = int(self.hg2_target_zw.get())
        zones_z = int(self.hg2_target_zl.get())
        zone_size = 128
        raw = np.fromfile(path, dtype="<u2") & 0x0FFF
        expected = zones_x * zones_z * zone_size * zone_size
        if raw.size != expected:
            raise ValueError(
                f"HGT size mismatch: expected {expected * 2} bytes for "
                f"{zones_x}x{zones_z} zones, found {raw.size * 2}"
            )
        heights = np.empty((zones_z * zone_size, zones_x * zone_size), dtype=np.uint16)
        cursor = 0
        zone_samples = zone_size * zone_size
        for zone_z in range(zones_z):
            for zone_x in range(zones_x):
                zone = raw[cursor : cursor + zone_samples].reshape((zone_size, zone_size))
                z0, x0 = zone_z * zone_size, zone_x * zone_size
                heights[z0 : z0 + zone_size, x0 : x0 + zone_size] = zone
                cursor += zone_samples
        return heights.astype(np.float32), zones_x, zones_z

    def _read_image_for_painter(self, path):
        zones_x = int(self.hg2_target_zw.get())
        zones_z = int(self.hg2_target_zl.get())
        if zones_x <= 0 or zones_z <= 0:
            raise ValueError("Set valid HG2 zone dimensions before painting an image.")

        img = Image.open(path)
        mode = img.mode
        legacy = self.hg2img_compat.get() and mode not in ("I;16", "I;16B", "I;16L", "I")
        if legacy:
            rgba = np.asarray(img.convert("RGBA"), dtype=np.uint8)
            red = rgba[..., 0].astype(np.uint16)
            green = rgba[..., 1].astype(np.uint16)
            if self.hg2img_precision.get() and red.max() <= 15:
                heights = (green << 4) | (red & 0x0F)
            else:
                heights = green << 4
            # HG2IMG's image representation is vertically flipped relative to
            # the south-to-north row order used by HG2/MAT storage.
            heights = np.flipud(heights)
        else:
            if mode in ("I;16", "I;16B", "I;16L", "I"):
                source = np.asarray(img.convert("I;16"), dtype=np.uint16).astype(np.float32)
                heights = np.rint(source / 65535.0 * PAINTER_MAX_ELEVATION_DM).astype(np.uint16)
            else:
                source = np.asarray(img.convert("L"), dtype=np.uint8).astype(np.float32)
                heights = np.rint(source / 255.0 * PAINTER_MAX_ELEVATION_DM).astype(np.uint16)

        if heights.shape[1] % zones_x or heights.shape[0] % zones_z:
            raise ValueError(
                f"Image size {heights.shape[1]}x{heights.shape[0]} is not divisible by "
                f"the configured {zones_x}x{zones_z} zone layout."
            )
        return heights.astype(np.float32), zones_x, zones_z

    def _painter_trn_config(self, source_path):
        explicit = getattr(self, "paint_trn_config", None)
        if explicit is not None:
            return explicit
        adjacent = os.path.splitext(source_path)[0] + ".trn"
        if os.path.exists(adjacent):
            try:
                return parse_trn_painter(adjacent)
            except Exception:
                pass
        return None

    def run_auto_painter(self):
        source_path = self.hg2_path.get()
        if not source_path:
            core.messagebox.showerror("Error", "Please select an input image/HG2 first.")
            return

        warnings = validate_paint_rules(self.paint_rules)
        if warnings:
            core.messagebox.showerror("Paint Rules", "\n".join(warnings[:12]))
            return

        try:
            lower = source_path.lower()
            if lower.endswith(".hg2"):
                header, heights = read_hg2(source_path)
                arr = heights.astype(np.float32)
                zones_x, zones_z = header.zones_x, header.zones_z
            elif lower.endswith(".hgt"):
                arr, zones_x, zones_z = self._read_hgt_for_painter(source_path)
            else:
                arr, zones_x, zones_z = self._read_image_for_painter(source_path)

            trn = self._painter_trn_config(source_path)
            transitions = trn.transitions if trn and trn.transitions else None
            min_x = trn.min_x if trn else 0.0
            min_z = trn.min_z if trn else 0.0
            world_width = trn.width if trn and trn.width else zones_x * 1280.0
            world_depth = trn.depth if trn and trn.depth else zones_z * 1280.0

            mat_data, stats = generate_mat(
                arr,
                self.paint_rules,
                zones_x=zones_x,
                zones_z=zones_z,
                transitions=transitions,
                bzn_paths=self.bzn_paths,
                min_x=min_x,
                min_z=min_z,
                world_width=world_width,
                world_depth=world_depth,
            )

            save_path = core.filedialog.asksaveasfilename(
                defaultextension=".mat",
                filetypes=[("Material Map", "*.mat")],
            )
            if save_path:
                write_mat(save_path, mat_data, zones_x, zones_z)
                notes = []
                if stats.ambiguous_tiles:
                    notes.append(f"{stats.ambiguous_tiles} ambiguous junctions -> material 0")
                if stats.unsupported_transition_tiles:
                    notes.append(
                        f"{stats.unsupported_transition_tiles} unsupported TRN transitions -> material 0"
                    )
                if stats.unmatched_samples:
                    notes.append(f"{stats.unmatched_samples} height samples matched no rule")
                suffix = ("\n\nWarnings:\n- " + "\n- ".join(notes)) if notes else ""
                core.messagebox.showinfo(
                    "Success",
                    f"Saved {save_path}\n"
                    f"MAT: {zones_x}x{zones_z} zones, "
                    f"{mat_data.shape[1]}x{mat_data.shape[0]} entries\n"
                    f"Solids {stats.solid_tiles} | Caps {stats.cap_tiles} | "
                    f"Diagonals {stats.diagonal_tiles}{suffix}",
                )
        except Exception as exc:
            core.messagebox.showerror("Error", f"Failed: {exc}")

    def load_auto_painter_config(self):
        path = core.filedialog.askopenfilename(
            filetypes=[("Paint Config", "*.trn *.ini *.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            config = parse_trn_painter(path)
            self.paint_trn_config = config
            if config.layers:
                if core.messagebox.askyesno(
                    "Load Painter Rules",
                    f"Found {len(config.layers)} [LayerN] painter rules. Replace existing rules?",
                ):
                    self.paint_rules = [dict(layer) for layer in config.layers]
                    self.refresh_rules_list()
            else:
                core.messagebox.showwarning(
                    "TRN Loaded",
                    "No [LayerN] MakeTRN painter rules were found. Existing paint rules were kept.\n\n"
                    f"Loaded {len(config.texture_types)} TextureTypes and "
                    f"{len(config.transitions)} directional transition pairs for MAT validation.",
                )
                return

            core.messagebox.showinfo(
                "Painter Config Loaded",
                f"Rules: {len(config.layers)}\n"
                f"TextureTypes: {len(config.texture_types)}\n"
                f"Directional transitions: {len(config.transitions)}",
            )
        except Exception as exc:
            core.messagebox.showerror("Error", f"Failed to parse painter config: {exc}")

    def validate_rules(self):
        warnings = validate_paint_rules(self.paint_rules)
        config = getattr(self, "paint_trn_config", None)
        if config and config.texture_types:
            available = set(config.texture_types)
            for i, rule in enumerate(self.paint_rules):
                material = int(rule.get("mat_id", -1))
                if material not in available:
                    warnings.append(
                        f"Rule {i} (Mat{material}): material is not defined by the loaded TRN"
                    )
        if warnings:
            core.messagebox.showwarning("Validation Issues", "\n".join(warnings[:12]))
        else:
            extra = ""
            if config:
                extra = f"\nTRN transition pairs available: {len(config.transitions)}"
            core.messagebox.showinfo(
                "Validation",
                "Rules are valid for MakeTRN units (height=decimeters, slope=degrees)." + extra,
            )

    def auto_balance_rules(self):
        if not self.paint_rules:
            return
        count = len(self.paint_rules)
        chunk = PAINTER_MAX_ELEVATION_DM / count
        for i, rule in enumerate(self.paint_rules):
            rule["min_h"] = float(i * chunk)
            rule["max_h"] = float((i + 1) * chunk)
            rule["min_s"] = 0.0
            rule["max_s"] = 90.0
        self.refresh_rules_list()
        core.messagebox.showinfo(
            "Auto-Balance",
            f"Balanced {count} rules across 0-{int(PAINTER_MAX_ELEVATION_DM)} decimeters "
            "(0-409.5 m).",
        )

    def _generate_stock_map_worker(self, cfg):
        # Keep the existing TRN/template generation, then replace its legacy
        # depth-7 flat HG2 with the Redux depth-8 format proven by the corpus.
        super()._generate_stock_map_worker(cfg)
        try:
            zones = cfg["zones"]
            zone_size = 1 << DEFAULT_ZONE_BITS
            heights = np.zeros(
                (zones * zone_size, zones * zone_size),
                dtype=np.uint16,
            )
            hg2_path = os.path.join(cfg["out_dir"], f"{cfg['name']}.hg2")
            write_hg2(
                hg2_path,
                heights,
                zones_x=zones,
                zones_z=zones,
                zone_bits=DEFAULT_ZONE_BITS,
            )
            self.log(
                "HG2 normalized to Redux 256x256 samples per zone.",
                "success",
            )
        except Exception as exc:
            self.log(f"HG2 normalization error: {exc}", "error")


if __name__ == "__main__":
    root = core.tk.Tk()
    app = BZ98TRNArchitect(root)
    root.mainloop()
