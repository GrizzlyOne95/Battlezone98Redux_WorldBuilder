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
from mission_visualizer import (
    extract_terrain_name,
    hg2_north_up,
    hg2_world_size,
    resolve_companion_hg2,
    resolve_mission_trn,
    world_to_canvas,
)


_BaseArchitect = core.BZ98TRNArchitect


class BZ98TRNArchitect(_BaseArchitect):
    """World Builder with canonical Battlezone 98 Redux HG2 I/O."""

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

    def _load_mission_background(self, path, *, redraw=True):
        """Load a mission background and retain its authoritative world geometry."""
        if path.lower().endswith(".hg2"):
            header, heights = read_hg2(path)
            display_heights = hg2_north_up(heights)
            peak = max(int(display_heights.max()), 1)
            arr_norm = np.clip(
                display_heights.astype(np.float32) / float(peak) * 255.0,
                0,
                255,
            ).astype(np.uint8)
            img = Image.fromarray(arr_norm)
            world_width, world_depth = hg2_world_size(header)
            self.mission_bg_world_width = world_width
            self.mission_bg_world_depth = world_depth
            self.mission_bg_hg2_header = header
        else:
            img = Image.open(path).convert("L")
            self.mission_bg_world_width = None
            self.mission_bg_world_depth = None
            self.mission_bg_hg2_header = None

        self.mission_bg_img = img
        self.mission_bg_source = os.path.abspath(path)
        if redraw:
            self.redraw_mission_canvas()

    def browse_mission_bg(self):
        path = core.filedialog.askopenfilename(
            filetypes=[("Map Image", "*.hg2 *.png *.bmp *.jpg")]
        )
        if not path:
            return

        try:
            self._load_mission_background(path)
        except Exception as exc:
            core.messagebox.showerror("Error", f"Failed to load map: {exc}")

    def _fallback_mission_world_size(self):
        try:
            size = float(self.selected_preset.get().split("(")[1].split("m")[0])
        except Exception:
            size = 5120.0
        return size, size

    def load_mission_overlay(self):
        bzn_path = core.filedialog.askopenfilename(
            title="Select Mission File (ASCII)",
            filetypes=[("Battlezone Mission", "*.bzn")],
        )
        if not bzn_path:
            return

        try:
            terrain_name = extract_terrain_name(bzn_path)
            trn_path = resolve_mission_trn(bzn_path, terrain_name)
            trn_data = core.TRNParser.parse(str(trn_path)) if trn_path else {}

            self.min_x = float(trn_data.get("MinX", 0.0) or 0.0)
            self.min_z = float(trn_data.get("MinZ", 0.0) or 0.0)

            # Object extraction remains the established ASCII parser. The
            # mission visualizer no longer guesses terrain geometry from it.
            self.mission_objects, self.ai_paths = core.BZNParser.parse(bzn_path)

            companion_hg2 = resolve_companion_hg2(trn_path)
            if self.mission_bg_img is None and companion_hg2 is not None:
                self._load_mission_background(str(companion_hg2), redraw=False)

            trn_width = trn_data.get("Width")
            trn_depth = trn_data.get("Depth")
            trn_width = float(trn_width) if trn_width else None
            trn_depth = float(trn_depth) if trn_depth else None

            bg_width = getattr(self, "mission_bg_world_width", None)
            bg_depth = getattr(self, "mission_bg_world_depth", None)
            fallback_width, fallback_depth = self._fallback_mission_world_size()

            self.mission_world_width = trn_width or bg_width or fallback_width
            self.mission_world_depth = trn_depth or bg_depth or fallback_depth

            warnings = []
            if trn_path is None:
                warnings.append("TRN not found; using HG2/preset dimensions.")
            if (
                trn_width
                and trn_depth
                and bg_width
                and bg_depth
                and (
                    abs(trn_width - bg_width) > 0.01
                    or abs(trn_depth - bg_depth) > 0.01
                )
            ):
                warnings.append(
                    "TRN/HG2 size mismatch: "
                    f"TRN {trn_width:g}x{trn_depth:g}, "
                    f"HG2 {bg_width:g}x{bg_depth:g}."
                )

            bg_source = getattr(self, "mission_bg_source", None)
            if companion_hg2 is not None and bg_source:
                if os.path.normcase(os.path.abspath(str(companion_hg2))) != os.path.normcase(
                    os.path.abspath(bg_source)
                ):
                    warnings.append("Loaded background differs from the BZN terrain HG2.")

            info_lines = [
                f"TerrainName: {terrain_name or 'N/A'}",
                f"TRN: {os.path.basename(str(trn_path)) if trn_path else 'N/A'}",
                f"MinX: {self.min_x:g}, MinZ: {self.min_z:g}",
                f"World: {self.mission_world_width:g} x {self.mission_world_depth:g}",
                f"Objects: {len(self.mission_objects)}",
                f"Paths: {len(self.ai_paths)}",
            ]
            if getattr(self, "mission_bg_source", None):
                info_lines.append(f"Background: {os.path.basename(self.mission_bg_source)}")
            if warnings:
                info_lines.append("")
                info_lines.extend(f"WARNING: {warning}" for warning in warnings)

            self.mission_info.config(state="normal")
            self.mission_info.delete("1.0", "end")
            self.mission_info.insert("1.0", "\n".join(info_lines))
            self.mission_info.config(state="disabled")
            self.redraw_mission_canvas()

        except ValueError as exc:
            core.messagebox.showerror("Error", str(exc))
        except Exception as exc:
            core.messagebox.showerror("Error", f"Failed to load mission: {exc}")

    def draw_mission_objects_on_canvas(self, canvas):
        if not hasattr(self, "map_draw_rect"):
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            self.map_draw_rect = (cw // 2 - 250, ch // 2 - 250, 500, 500)

        world_width = getattr(self, "mission_world_width", None)
        world_depth = getattr(self, "mission_world_depth", None)
        if not world_width or not world_depth:
            world_width = getattr(self, "mission_bg_world_width", None)
            world_depth = getattr(self, "mission_bg_world_depth", None)
        if not world_width or not world_depth:
            world_width, world_depth = self._fallback_mission_world_size()

        min_x = float(getattr(self, "min_x", 0.0))
        min_z = float(getattr(self, "min_z", 0.0))

        for path in getattr(self, "ai_paths", []) or []:
            points = path.get("points", [])
            if len(points) < 2:
                continue
            polyline = []
            for point in points:
                try:
                    px, pz = point[0], point[1]
                    cx, cy = world_to_canvas(
                        px,
                        pz,
                        min_x=min_x,
                        min_z=min_z,
                        world_width=world_width,
                        world_depth=world_depth,
                        draw_rect=self.map_draw_rect,
                    )
                    polyline.extend((cx, cy))
                except (TypeError, ValueError, IndexError):
                    continue
            if len(polyline) >= 4:
                canvas.create_line(*polyline, fill=core.BZ_CYAN, width=1)

        for obj in getattr(self, "mission_objects", []) or []:
            try:
                wx = obj["pos"][0]
                wz = obj["pos"][2]
                cx, cy = world_to_canvas(
                    wx,
                    wz,
                    min_x=min_x,
                    min_z=min_z,
                    world_width=world_width,
                    world_depth=world_depth,
                    draw_rect=self.map_draw_rect,
                )
            except (KeyError, TypeError, ValueError, IndexError):
                continue

            color = core.BZ_GREEN
            cls = obj.get("odf", "").lower()
            if "recycle" in cls or "cons" in cls:
                color = "#ffee00"
            elif "fact" in cls:
                color = "#ff8800"
            elif "turr" in cls or "tow" in cls:
                color = "#ff4444"
            elif "scav" in cls:
                color = "#0088ff"

            canvas.create_rectangle(cx - 2, cy - 2, cx + 2, cy + 2, fill=color, outline="")

    def run_auto_painter(self):
        source_path = self.hg2_path.get()
        if not source_path:
            core.messagebox.showerror("Error", "Please select an input image/HG2 first.")
            return

        try:
            if source_path.lower().endswith(".hg2"):
                _, heights = read_hg2(source_path)
                arr = heights.astype(np.float32)
            else:
                img = Image.open(source_path).convert("I;16")
                arr = np.array(img).astype(np.float32)
                arr = (arr / 65535.0) * 4095.0

            mat_data = core.AutoPainter.generate_mat(
                arr,
                self.paint_rules,
                bzn_paths=self.bzn_paths,
            )

            save_path = core.filedialog.asksaveasfilename(
                defaultextension=".mat",
                filetypes=[("Material Map", "*.mat")],
            )
            if save_path:
                with open(save_path, "wb") as stream:
                    stream.write(mat_data.tobytes())
                core.messagebox.showinfo("Success", f"Saved {save_path}")
        except Exception as exc:
            core.messagebox.showerror("Error", f"Failed: {exc}")

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
