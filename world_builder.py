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
