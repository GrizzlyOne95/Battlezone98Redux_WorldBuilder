import os
import math
import random
import re
import numpy as np
import struct
import imageio
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageDraw, ImageFilter, ImageTk, ImageOps, ImageEnhance
from scipy.ndimage import map_coordinates

class BZ98TRNArchitect:
    def __init__(self, root):
        self.root = root # Keep reference to main root
        self.root.title("BZ98 Redux: World Builder Suite (V3.3)")
        self.root.geometry("1400x950")

        # --- Variables ---
        self.planet_var = tk.StringVar(value="AC")
        self.tile_res_var = tk.IntVar(value=512)
        # self.synthetic_mode = tk.BooleanVar(value=True)
        self.style_var = tk.StringVar(value="Square/Blocky")
        self.depth_var = tk.DoubleVar(value=0.10)
        self.teeth_count = tk.IntVar(value=12)
        self.jitter_var = tk.DoubleVar(value=0.0)
        self.blend_softness = tk.IntVar(value=0)
        self.seed_var = tk.IntVar(value=random.randint(0, 99999))
        self.sky_input_path = tk.StringVar()
        self.sky_out_res = tk.IntVar(value=1024)
        self.zoom_level = 1.0
        self.trans_mode_var = tk.StringVar(value="Linear")
        self.trans_mode_var.trace_add("write", self.update_preview)
        
        self.export_dds = tk.BooleanVar(value=False)
        self.export_mat = tk.BooleanVar(value=True)
        self.export_trn = tk.BooleanVar(value=True)
        
        # HG2 Conversion Control Variables
        self.hg2_target_zw = tk.IntVar(value=8) # Default 8 zones wide
        self.hg2_target_zl = tk.IntVar(value=8) # Default 8 zones long
        self.hg2_brightness = tk.DoubleVar(value=1.0)
        self.hg2_contrast = tk.DoubleVar(value=1.0)
        self.hg2_smooth_val = tk.IntVar(value=0)

        # Export Toggles
        self.exp_png = tk.BooleanVar(value=True)
        self.exp_csv = tk.BooleanVar(value=True)
        self.exp_trn = tk.BooleanVar(value=True)
        
        self.source_dir = ""
        self.groups = {} 
        self.full_atlas_preview = None
        self.preview_tk = None

        self.setup_ui()
        self.bind_events()
        
    def browse_hg2(self):
        path = filedialog.askopenfilename(filetypes=[("Heightmaps", "*.hg2 *.png *.bmp")])
        if path:
            self.hg2_path.set(path)
            # Auto-detect dimensions if it's an HG2
            if path.lower().endswith(".hg2"):
                try:
                    with open(path, "rb") as f:
                        header = f.read(12)
                        _, _, z_w, z_l, _, _ = struct.unpack("<HHHHHH", header)
                        self.hg2_target_zw.set(z_w)
                        self.hg2_target_zl.set(z_l)
                except:
                    pass

    def convert_hg2_to_png(self):
        path = self.hg2_path.get()
        if not path or not os.path.exists(path):
            return
        
        try:
            with open(path, "rb") as f:
                header = f.read(12)
                f_v, depth, z_w, z_l, f_r, _ = struct.unpack("<HHHHHH", header)
                
                zone_size = 2**depth
                full_w, full_h = z_w * zone_size, z_l * zone_size
                
                raw_data = np.frombuffer(f.read(), dtype=np.uint16)
                img_array = np.zeros((full_h, full_w), dtype=np.uint16)
                
                idx = 0
                for zy in range(z_l):
                    for zx in range(z_w):
                        start_x, start_y = zx * zone_size, zy * zone_size
                        zone_data = raw_data[idx : idx + (zone_size * zone_size)]
                        if zone_data.size == (zone_size * zone_size):
                            img_array[start_y:start_y+zone_size, start_x:start_x+zone_size] = \
                                zone_data.reshape((zone_size, zone_size))
                        idx += (zone_size * zone_size)

                # Visibility Normalization
                v_min, v_max = img_array.min(), img_array.max()
                if v_max > v_min:
                    norm_data = (img_array.astype(np.float32) - v_min) / (v_max - v_min)
                    img_array = (norm_data * 65535).astype(np.uint16)

                out_path = path.replace(".hg2", "_edit.png")
                out_img = Image.fromarray(img_array).convert("I;16")

                # --- APPLY 90 DEGREE CCW ROTATION ---
                out_img = out_img.transpose(Image.ROTATE_90)

                out_img.save(out_path)
                messagebox.showinfo("Success", f"Converted & Rotated 90° CCW\nRes: {out_img.width}x{out_img.height}")
        except Exception as e:
            messagebox.showerror("Error", f"Conversion failed: {e}")

    def convert_png_to_hg2(self):
        path = self.hg2_path.get()
        if not path or not os.path.exists(path): return
        
        try:
            # 1. Load the 16-bit PNG
            img = Image.open(path).convert("I;16")
            
            # 2. Dynamic Dimensions Calculation
            z_w = getattr(self, 'hg2_target_zw', tk.IntVar(value=8)).get()
            z_l = getattr(self, 'hg2_target_zl', tk.IntVar(value=8)).get()
            
            # Calculate zone_size based on image width and number of zones
            # This prevents the 512 -> 2048 scaling issue
            zone_size = img.width // z_w 
            
            # Determine depth for the HG2 header (2^depth = zone_size)
            # e.g., 64px = depth 6, 128px = depth 7, 256px = depth 8
            depth = int(math.log2(zone_size))
            
            # 3. Rotate BACK (90° CW)
            img = img.transpose(Image.ROTATE_270)
            
            # 4. Apply Adjusters (Brightness/Contrast/Smoothing)
            arr = np.array(img).astype(np.float32)
            if hasattr(self, 'hg2_brightness'):
                arr *= self.hg2_brightness.get()
            if hasattr(self, 'hg2_contrast'):
                mean = 32768.0
                arr = (arr - mean) * self.hg2_contrast.get() + mean
            
            # Smoothing fix for Pillow mode compatibility
            if hasattr(self, 'hg2_smooth_val') and self.hg2_smooth_val.get() > 0:
                img_proc = Image.fromarray((arr / 256).astype(np.uint8)).convert("RGB")
                img_proc = img_proc.filter(ImageFilter.GaussianBlur(self.hg2_smooth_val.get()))
                img_final_arr = np.array(img_proc.convert("L")).astype(np.float32) * 256
            else:
                img_final_arr = arr

            # 5. Convert to uint16 Array for binary packing
            img_final_arr = np.clip(img_final_arr, 0, 65535).astype(np.uint16)
            h, w = img_final_arr.shape 
            
            # 6. Construct 12-byte HG2 Header using the calculated depth
            # Format: version, depth, width_zones, length_zones, fixed_val, padding
            header = struct.pack("<HHHHHH", 1, depth, z_w, z_l, 10, 0)
            
            # 7. Pack data into zones
            output_data = bytearray()
            for zy in range(z_l):
                for zx in range(z_w):
                    zone = img_final_arr[zy*zone_size : (zy+1)*zone_size, zx*zone_size : (zx+1)*zone_size]
                    output_data.extend(zone.tobytes())
            
            out_path = path.rsplit('.', 1)[0] + "_export.hg2"
            with open(out_path, "wb") as f:
                f.write(header)
                f.write(output_data)
                    
            messagebox.showinfo("Success", f"Exported {z_w}x{z_l} HG2 (Zone Size: {zone_size})")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save HG2: {e}")
        
    # --- THE MISSING METHOD ---
    def create_fine_tune_slider(self, parent, label, var, from_, to, res=1.0):
        frame = tk.Frame(parent)
        frame.pack(fill="x", pady=2)
        tk.Label(frame, text=label, font=("Arial", 9)).pack(side="top", anchor="w")
        inner = tk.Frame(frame)
        inner.pack(fill="x")
        
        def adjust(delta):
            val = var.get() + delta
            var.set(round(max(from_, min(to, val)), 3))
            self.update_preview()

        tk.Button(inner, text="<", command=lambda: adjust(-res), width=2).pack(side="left")
        scale = tk.Scale(inner, from_=from_, to=to, resolution=res, orient="horizontal", 
                         variable=var, command=self.force_refresh, showvalue=True)
        scale.pack(side="left", fill="x", expand=True)
        tk.Button(inner, text=">", command=lambda: adjust(res), width=2).pack(side="left")

    def setup_ui(self):
        # 1. Create Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both")

        # 2. Setup TAB 1 (Atlas Generator)
        self.tab_trn = tk.Frame(self.notebook)
        self.notebook.add(self.tab_trn, text=" Atlas Creator ")

        # --- TAB 1 CONTROLS ---
        ctrls = tk.Frame(self.tab_trn, padx=15, pady=15, width=350)
        ctrls.pack(side="left", fill="y")

        tk.Label(ctrls, text="PLANET CONFIG", font=("Arial", 11, "bold")).pack(anchor="w")
        tk.Entry(ctrls, textvariable=self.planet_var, width=10).pack(anchor="w", pady=2)
        
        tk.Label(ctrls, text="DESIRED TILE SIZE:").pack(anchor="w", pady=(10,0))
        res_opts = [256, 512, 1024, 2048, 4096]
        self.res_dropdown = ttk.Combobox(ctrls, textvariable=self.tile_res_var, values=res_opts, state="readonly")
        self.res_dropdown.pack(fill="x", pady=5)

        ttk.Separator(ctrls, orient="horizontal").pack(fill="x", pady=10)

        tk.Label(ctrls, text="PATTERN ENGINE", font=("Arial", 11, "bold")).pack(anchor="w")
        # tk.Checkbutton(ctrls, text="Synthetic Mode", variable=self.synthetic_mode, command=self.on_mode_change).pack(anchor="w")
        
        tk.Label(ctrls, text="TRANSITION LOGIC:").pack(anchor="w", pady=(10,0))
        ttk.Combobox(ctrls, textvariable=self.trans_mode_var, 
             values=["Linear", "Matrix"], state="readonly").pack(fill="x", pady=5)
        
        self.style_dropdown = ttk.Combobox(ctrls, textvariable=self.style_var, state="readonly")
        self.style_dropdown.pack(fill="x", pady=5)

        self.create_fine_tune_slider(ctrls, "Edge Depth:", self.depth_var, 0.0, 0.5, 0.01)
        self.create_fine_tune_slider(ctrls, "Frequency (Teeth/Size):", self.teeth_count, 2, 80, 1)
        self.create_fine_tune_slider(ctrls, "Random Jitter:", self.jitter_var, 0.0, 50.0, 0.5)
        self.create_fine_tune_slider(ctrls, "Feathering (Blur):", self.blend_softness, 0, 50, 1)

        tk.Button(ctrls, text="🎲 NEW SEED", bg="#f0f0f0", command=self.cycle_seed).pack(fill="x", pady=5)
        self.info_label = tk.Label(ctrls, text="Atlas Size: 0x0", fg="gray")
        self.info_label.pack(fill="x", pady=5)

        ttk.Separator(ctrls, orient="horizontal").pack(fill="x", pady=15)
        tk.Checkbutton(ctrls, text="Export PNG", variable=self.exp_png).pack(anchor="w")
        tk.Checkbutton(ctrls, text="Export CSV", variable=self.exp_csv).pack(anchor="w")
        tk.Checkbutton(ctrls, text="Export TRN", variable=self.exp_trn).pack(anchor="w")

        tk.Button(ctrls, text="1. SELECT FOLDER", command=self.browse, bg="#9e9e9e", height=2).pack(fill="x", pady=(15,5))
        # Small Tip Label
        tk.Label(ctrls, text="💡 Tip: Folder should contain .dds or .png source textures\nnamed like S0.dds for solid 0, S1.dds for solid 1,\n or S0_B.dds for a variation of Solid 0.\nThe program will handle transitions so you only need solids texture sources.", 
                 font=("Arial", 8, "italic"), fg="#757575", wraplength=300).pack(anchor="w", pady=(2, 5))
        tk.Button(ctrls, text="2. BUILD ATLAS", command=self.generate, bg="#2e7d32", fg="white", font=("Arial", 10, "bold")).pack(fill="x")

        # --- TAB 1 PREVIEW ---
        pre_frame = tk.Frame(self.tab_trn, bg="#111")
        pre_frame.pack(side="right", expand=True, fill="both")
        self.canvas = tk.Canvas(pre_frame, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(side="left", expand=True, fill="both")

        # 3. Setup TAB 2 (World Builder Tools)
        self.tab_world = tk.Frame(self.notebook)
        self.notebook.add(self.tab_world, text=" World Builder Tools ")
        self.setup_world_tab()

        self.on_mode_change()

    def setup_world_tab(self):
        # Main container split into Left (Controls) and Right (Preview)
        container = tk.Frame(self.tab_world, padx=20, pady=20)
        container.pack(fill="both", expand=True)

        # --- LEFT PANEL: CONTROLS ---
        left_panel = tk.Frame(container, width=450)
        left_panel.pack(side="left", fill="y", padx=(0, 20))

        # 1. Skybox Section Header
        tk.Label(left_panel, text="SKYBOX & HG2 TOOLS", font=("Arial", 14, "bold")).pack(anchor="w")
        
        # --- INPUT FRAME ---
        sky_frame = tk.LabelFrame(left_panel, text=" Input Panorama ", padx=10, pady=10)
        sky_frame.pack(fill="x", pady=5)

        tk.Entry(sky_frame, textvariable=self.sky_input_path).pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(sky_frame, text="Browse", command=self.browse_skybox_image).pack(side="left")

        # --- SETTINGS ---
        settings_frame = tk.Frame(left_panel)
        settings_frame.pack(fill="x", pady=5)
        
        tk.Label(settings_frame, text="Face Resolution:").pack(side="left")
        tk.OptionMenu(settings_frame, self.sky_out_res, 512, 1024, 2048).pack(side="left", padx=10)

        # --- NEW EXPORT OPTIONS ---
        export_options = tk.LabelFrame(left_panel, text=" Export Settings ", padx=10, pady=10)
        export_options.pack(fill="x", pady=10)

        tk.Checkbutton(export_options, text="Export as DDS", variable=self.export_dds).pack(anchor="w")
        tk.Checkbutton(export_options, text="Export Material (.mat)", variable=self.export_mat).pack(anchor="w")
        tk.Checkbutton(export_options, text="Export TRN Entry", variable=self.export_trn).pack(anchor="w")

        # --- THE EXPORT BUTTON ---
        tk.Button(left_panel, text="🚀 FINAL EXPORT", command=self.export_skybox, 
                  bg="#2e7d32", fg="white", font=("Arial", 11, "bold"), height=2).pack(fill="x", pady=10)

        # --- HELP TIP ---
        help_text = "Tip: High-res exports use Bicubic interpolation for the best quality. Previews use Linear for speed."
        tk.Label(left_panel, text=help_text, font=("Arial", 8, "italic"), fg="gray", wraplength=350).pack(pady=10)

        # --- RIGHT PANEL: HG2 PREVIEW ---
        right_panel = tk.Frame(container, bg="#111")
        right_panel.pack(side="right", expand=True, fill="both")
        
                # 2. HG2 Converter Section
        tk.Label(left_panel, text="HEIGHTMAP CONVERTER", font=("Arial", 14, "bold")).pack(anchor="w")
        hg2_frame = tk.LabelFrame(left_panel, text=" Terrain Settings ", padx=15, pady=15)
        hg2_frame.pack(fill="x", pady=10)

        self.hg2_path = tk.StringVar()
        # Trace path changes to update preview automatically
        self.hg2_path.trace_add("write", self.update_hg2_preview)
        
        tk.Entry(hg2_frame, textvariable=self.hg2_path).pack(fill="x", pady=2)
        tk.Button(hg2_frame, text="1. BROWSE HG2/PNG", command=self.browse_hg2).pack(fill="x", pady=5)

        # Fine-tune Sliders for the Exporter
        self.create_hg2_slider(hg2_frame, "Export Brightness:", self.hg2_brightness, 0.1, 2.0, 0.1)
        self.create_hg2_slider(hg2_frame, "Export Contrast:", self.hg2_contrast, 0.1, 2.0, 0.1)
        self.create_hg2_slider(hg2_frame, "Smoothing (Blur):", self.hg2_smooth_val, 0, 10, 1)

        # Export Buttons
        btn_frame = tk.Frame(hg2_frame)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="HG2 -> PNG", bg="#0288d1", fg="white",
                  command=self.convert_hg2_to_png).pack(side="left", expand=True, fill="x", padx=(0,5))
        tk.Button(btn_frame, text="PNG -> HG2", bg="#f57c00", fg="white",
                  command=self.convert_png_to_hg2).pack(side="left", expand=True, fill="x", padx=(5,0))

        # --- RIGHT PANEL: LIVE PREVIEW ---
        right_panel = tk.LabelFrame(container, text=" Heightmap Visualizer (Normalized 8-bit) ", bg="#111")
        right_panel.pack(side="right", expand=True, fill="both")

        self.hg2_preview_canvas = tk.Canvas(right_panel, bg="#050505", highlightthickness=0)
        self.hg2_preview_canvas.pack(expand=True, fill="both", padx=10, pady=10)

    def create_hg2_slider(self, parent, label, var, from_, to, res):
        """Helper to create sliders that trigger the preview update"""
        tk.Label(parent, text=label, font=("Arial", 9)).pack(anchor="w")
        s = tk.Scale(parent, from_=from_, to=to, resolution=res, orient="horizontal", 
                     variable=var, command=self.update_hg2_preview)
        s.pack(fill="x", pady=(0, 8))

    def update_hg2_preview(self, *args):
        path = self.hg2_path.get()
        if not path or not os.path.exists(path): return

        try:
            if path.lower().endswith(".hg2"):
                with open(path, "rb") as f:
                    header = f.read(12)
                    _, depth, x_zones, z_zones, _, _ = struct.unpack("<HHHHHH", header)
                    z_width = 2**depth
                    raw_data = np.frombuffer(f.read(), dtype=np.uint16)
                    
                    full_w, full_h = x_zones * z_width, z_zones * z_width
                    arr = np.zeros((full_h, full_w), dtype=np.float32)
                    
                    idx = 0
                    for zy in range(z_zones):
                        for zx in range(x_zones):
                            zone_size = z_width * z_width
                            zone_block = raw_data[idx:idx+zone_size].reshape((z_width, z_width))
                            arr[zy*z_width:(zy+1)*z_width, zx*z_width:(zx+1)*z_width] = zone_block
                            idx += zone_size
            else:
                img_input = Image.open(path).convert("I;16")
                arr = np.array(img_input).astype(np.float32)

            # Apply Adjusters
            arr *= self.hg2_brightness.get()
            mean = 32768.0
            arr = (arr - mean) * self.hg2_contrast.get() + mean
            
            # High-precision blur in Mode F (prevents banding)
            temp_img = Image.fromarray(arr, mode='F')
            if self.hg2_smooth_val.get() > 0:
                temp_img = temp_img.filter(ImageFilter.GaussianBlur(self.hg2_smooth_val.get()))
            
            final_arr = np.array(temp_img)
            
            # Better Normalization for UI (prevents stepping/banding)
            f_min, f_max = final_arr.min(), final_arr.max()
            if f_max > f_min:
                norm_arr = (final_arr - f_min) / (f_max - f_min)
            else:
                norm_arr = final_arr / 65535.0
                
            preview_8bit = Image.fromarray((norm_arr * 255).astype(np.uint8))
            
            cw = self.hg2_preview_canvas.winfo_width()
            ch = self.hg2_preview_canvas.winfo_height()
            if cw < 10: cw, ch = 600, 600
            
            preview_8bit.thumbnail((cw, ch), Image.Resampling.LANCZOS)
            self.hg2_tk_photo = ImageTk.PhotoImage(preview_8bit)
            self.hg2_preview_canvas.delete("all")
            self.hg2_preview_canvas.create_image(cw//2, ch//2, image=self.hg2_tk_photo)
            
        except Exception as e:
            print(f"Preview Update Error: {e}")

    def bind_events(self):
        self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B1-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas.bind("<MouseWheel>", self.zoom_wheel)
        self.canvas.bind("<Button-4>", self.zoom_wheel)
        self.canvas.bind("<Button-5>", self.zoom_wheel)
        
    def browse_skybox_image(self):
        ftypes = [
            ("All Supported", "*.png *.jpg *.jpeg *.dds *.tga *.hdr *.exr"),
            ("Standard Images", "*.png *.jpg *.jpeg"),
            ("DirectDraw Surface", "*.dds"),
            ("Truevision TGA", "*.tga"),
            ("HDR Formats", "*.hdr *.exr")
        ]
        path = filedialog.askopenfilename(filetypes=ftypes)
        if path:
            self.sky_input_path.set(path)
            # Trigger the preview immediately after setting the path
            self.process_skybox()

    def process_skybox(self):
        """Generates a 256px 4x3 cross preview instantly."""
        path = self.sky_input_path.get()
        if not path or not os.path.exists(path):
            return

        try:
            # 1. Load and prepare image data
            img_data = np.array(Image.open(path).convert("RGB"))
            img_float = img_data.astype(np.float32)
            
            # 2. Settings
            self.rotation_rad = np.pi # Default 180 deg orientation
            preview_res = 256 # Low res for speed
            
            face_map = {0: 'pz', 1: 'nz', 2: 'px', 3: 'nx', 4: 'py', 5: 'ny'}
            self.generated_faces = {} 

            # 3. Generate preview faces using Order 1 (Linear)
            for i in range(6):
                face_arr = self.generate_cube_face(img_float, i, preview_res, order=1)
                face_arr = np.clip(face_arr, 0, 255).astype(np.uint8)
                key = face_map[i]
                self.generated_faces[key] = Image.fromarray(face_arr)

            # 4. Update the UI
            self.update_skybox_preview(self.generated_faces)
            
        except Exception as e:
            messagebox.showerror("Preview Error", f"Could not generate preview: {str(e)}")

    def export_skybox(self):
        """High-quality export using full resolution and Order 3 (Bicubic)."""
        path = self.sky_input_path.get()
        if not path or not hasattr(self, 'generated_faces'):
            messagebox.showwarning("Warning", "Please load an image first.")
            return

        out_dir = filedialog.askdirectory(title="Select Export Folder")
        if not out_dir: return

        try:
            # Load original for high-res processing
            img_data = np.array(Image.open(path).convert("RGB")).astype(np.float32)
            res = self.sky_out_res.get()
            base_name = os.path.splitext(os.path.basename(path))[0]
            face_map = {0: 'pz', 1: 'nz', 2: 'px', 3: 'nx', 4: 'py', 5: 'ny'}

            # 1. Generate and Save High-Quality PNG faces
            for i in range(6):
                face_arr = self.generate_cube_face(img_data, i, res, order=3)
                face_arr = np.clip(face_arr, 0, 255).astype(np.uint8)
                face_key = face_map[i]
                img = Image.fromarray(face_arr)
                img.save(os.path.join(out_dir, f"{base_name}_{face_key}.png"))

            # 2. Export Material File
            if self.export_mat.get():
                with open(os.path.join(out_dir, f"{base_name}.mat"), "w") as f:
                    f.write(f"// Skybox Material\ntype skybox\n")
                    for k in face_map.values():
                        f.write(f"{k} {base_name}_{k}.png\n")

            # 3. Export TRN Entry
            if self.export_trn.get():
                with open(os.path.join(out_dir, f"{base_name}_entry.txt"), "w") as f:
                    f.write(f"[Skybox]\nName={base_name}\nRes={res}\n")

            messagebox.showinfo("Success", f"Exported to {out_dir}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def generate_cube_face(self, img, face_idx, res, order=3):
        grid = np.linspace(-1 + (1/res), 1 - (1/res), res)
        x_coords, y_coords = np.meshgrid(grid, grid)

        if face_idx == 0:   # pz
            x_p, y_p, z_p = np.full_like(x_coords, -1), -x_coords, -y_coords
        elif face_idx == 1: # nz
            x_p, y_p, z_p = np.full_like(x_coords, 1), x_coords, -y_coords
        elif face_idx == 2: # px
            x_p, y_p, z_p = x_coords, np.full_like(x_coords, -1), -y_coords
        elif face_idx == 3: # nx
            x_p, y_p, z_p = -x_coords, np.full_like(x_coords, 1), -y_coords
        elif face_idx == 4: # py
            x_p, y_p, z_p = -y_coords, -x_coords, np.full_like(x_coords, 1)
        elif face_idx == 5: # ny
            x_p, y_p, z_p = y_coords, -x_coords, np.full_like(x_coords, -1)
        
        r = np.sqrt(x_p**2 + y_p**2 + z_p**2)
        lat = np.acos(z_p / r)
        lon = np.arctan2(y_p, x_p) + self.rotation_rad
        lon = lon % (2 * np.pi) 

        in_h, in_w = img.shape[:2]
        u_img = (in_w * lon / (2 * np.pi) - 0.5)
        v_img = (in_h * lat / np.pi - 0.5)
        
        coords = np.array([v_img.ravel(), u_img.ravel()])
        channels = []
        for i in range(3):
            ch = map_coordinates(img[:,:,i], coords, order=order, mode='wrap').reshape(res, res)
            channels.append(ch)
            
        return np.stack(channels, axis=-1)

    def update_skybox_preview(self, face_dict):
        # Use the width of the face in the preview (e.g., 150px or res)
        res = next(iter(face_dict.values())).width 
        canvas_img = Image.new("RGB", (res * 4, res * 3), (30, 30, 30))

        layout = {
            'nx': (0, 1), 'pz': (1, 1), 'px': (2, 1), 'nz': (3, 1),
            'py': (1, 0), 'ny': (1, 2)
        }

        for face_key, grid_pos in layout.items():
            if face_key in face_dict:
                canvas_img.paste(face_dict[face_key], (grid_pos[0] * res, grid_pos[1] * res))

        cw, ch = self.hg2_preview_canvas.winfo_width(), self.hg2_preview_canvas.winfo_height()
        if cw < 10: cw, ch = 800, 600
        canvas_img.thumbnail((cw, ch), Image.Resampling.LANCZOS)
        self.hg2_tk_photo = ImageTk.PhotoImage(canvas_img)
        self.hg2_preview_canvas.delete("all")
        self.hg2_preview_canvas.create_image(cw//2, ch//2, image=self.hg2_tk_photo)

    def on_res_change(self, *args):
        if self.source_dir: self.browse(initial=False) # Reload images with new res
        self.update_preview()

    def cycle_seed(self):
        self.seed_var.set(random.randint(0, 99999))
        self.update_preview()

    def force_refresh(self, *args):
        self.update_preview()

    def on_mode_change(self, *args):
        all_styles = [
            "Square/Blocky", "Sawtooth", "Interlocking L", "Sine Wave", "Stairs/Steps",
            "Fractal Noise", "Soft Clouds", "Binary Dither", "Voronoi/Cells", 
            "Plasma/Circuit", "Radial/Impact"
        ]
        self.style_dropdown['values'] = all_styles
        if not self.style_var.get() in all_styles:
            self.style_var.set("Square/Blocky")
        self.update_preview()

    def zoom_wheel(self, event):
        if event.num == 4 or event.delta > 0: self.zoom_level *= 1.1
        else: self.zoom_level *= 0.9
        self.zoom_level = max(0.1, min(10.0, self.zoom_level))
        self.refresh_canvas()

    def generate_mask(self, mode="diag"):
        res = self.tile_res_var.get()
        style = self.style_var.get()
        random.seed(self.seed_var.get()) 
        
        # --- ENGINE A: VERTEX-BASED (Geometric) ---
        vertex_styles = ["Square/Blocky", "Sawtooth", "Interlocking L", "Sine Wave", "Stairs/Steps"]
        
        if style in vertex_styles:
            mask = Image.new("L", (res, res), 0)
            draw = ImageDraw.Draw(mask)
            depth_px = res * self.depth_var.get()
            count = max(1, self.teeth_count.get())
            jitter = self.jitter_var.get()

            # Fixed Tuple Assignment Logic
            if mode == "cap":
                line_start, line_end = (0, res * 0.75), (res, res * 0.75)
                fill_pts = [(res, res), (0, res)]
            else:
                line_start, line_end = (0, res), (res, 0)
                fill_pts = [(res, res)]
            
            pts = [line_start]
            for i in range(1, count + 1):
                t = i / count
                px = line_start[0] + (line_end[0] - line_start[0]) * t
                py = line_start[1] + (line_end[1] - line_start[1]) * t
                
                off = (depth_px if i % 2 == 0 else -depth_px) + random.uniform(-jitter, jitter)
                
                if style == "Square/Blocky":
                    pts.append(((line_start[0] + (line_end[0]-line_start[0]) * (i-0.9)/count) + off, py + off))
                    pts.append((px + off, py + off))
                elif style == "Sawtooth":
                    pts.append((px + off, py + off))
                elif style == "Sine Wave":
                    # Offset perpendicular to the line flow
                    s_val = math.sin(t * math.pi * 2) * depth_px
                    pts.append((px + s_val, py + s_val))
                elif style == "Stairs/Steps":
                    pts.append((px, py + off))
                    pts.append((px + (res/count), py + off))
                else: # Interlocking L
                    pts.append((px, py + off))
            
            pts.append(line_end)
            draw.polygon(pts + fill_pts, fill=255)

        # --- ENGINE B: FIELD-BASED (Organic/Noise) ---
        else:
            gradient = np.zeros((res, res), dtype=np.float32)
            for y in range(res):
                for x in range(res):
                    if style == "Radial/Impact":
                        # Circular gradient from bottom-right
                        dist = math.sqrt((res-x)**2 + (res-y)**2)
                        gradient[y, x] = dist / (res * 1.414)
                    elif mode == "cap":
                        gradient[y, x] = (y / res)
                    else:
                        gradient[y, x] = ((x + y) / (res * 2))
            
            influence = self.jitter_var.get() / 100.0
            freq = max(1, self.teeth_count.get())
            
            noise_img = Image.effect_noise((res, res), freq)
            noise_arr = np.array(noise_img).astype(np.float32) / 255.0
            
            if style == "Voronoi/Cells":
                noise_arr = np.round(noise_arr * (freq / 5)) / (freq / 5)
            elif style == "Plasma/Circuit":
                noise_arr = np.abs(np.sin(noise_arr * freq))
            
            warped = np.clip(gradient + (noise_arr - 0.5) * influence * 2, 0, 1)
            mask = Image.fromarray((warped * 255).astype(np.uint8))
            
            if style == "Soft Clouds":
                mask = mask.point(lambda p: 255 if p > 128 else 0)
            elif style == "Fractal Noise":
                mask = mask.point(lambda p: 255 if p > 128 else 0)
                crunch = Image.effect_noise((res, res), res // 4).point(lambda p: 255 if p > 220 else 0)
                mask = Image.composite(crunch, mask, mask.filter(ImageFilter.GaussianBlur(10)))
            elif style == "Binary Dither":
                mask = mask.convert("1").convert("L")
            else: # Default threshold
                mask = mask.point(lambda p: 255 if p > 128 else 0)

        blur = self.blend_softness.get()
        if blur > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(blur))
            
        return mask

    def browse(self, initial=True):
        if initial:
            self.source_dir = filedialog.askdirectory()
        if not self.source_dir: return
        res = self.tile_res_var.get(); self.groups = {}
        pattern = re.compile(r's(\d+)(?:_([a-z]))?', re.IGNORECASE)
        for f in sorted(os.listdir(self.source_dir)):
            match = pattern.search(f)
            if match:
                base_id = int(match.group(1)); var = match.group(2).upper() if match.group(2) else "A"
                if base_id not in self.groups: self.groups[base_id] = {}
                try: 
                    img = Image.open(os.path.join(self.source_dir, f)).convert("RGBA").resize((res, res), Image.LANCZOS)
                    self.groups[base_id][var] = img
                except: continue
        self.update_preview()

    def update_preview(self, *args):
        if not self.groups: return
        res = self.tile_res_var.get()
        mode = self.trans_mode_var.get()
        baked = []
        indices = sorted(self.groups.keys())
        c_m, d_m = self.generate_mask("cap"), self.generate_mask("diag")
        
# 1. Solids (Match the repeated index logic)
        for i in indices:
            for var in sorted(self.groups[i].keys()):
                baked.append(self.groups[i][var])
        
        # 2. Transitions (Linear vs Matrix logic)
        for idx, i in enumerate(indices):
            if mode == "Linear":
                targets = [indices[idx + 1]] if idx + 1 < len(indices) else []
            else: # Matrix mode
                targets = indices[idx + 1:]
                
            for j in targets:
                c_i = self.groups[i]["A"].copy()
                c_i.paste(self.groups[j]["A"], (0,0), c_m)
                d_i = self.groups[i]["A"].copy()
                d_i.paste(self.groups[j]["A"], (0,0), d_m)
                baked.append(c_i)
                baked.append(d_i)
        
        gs = math.ceil(math.sqrt(len(baked) + 1))
        total_size = gs * res
        
        # UI update for atlas size
        if total_size > 8192:
            self.info_label.config(text=f"CRITICAL: {total_size}px (Exceeds 8k!)", fg="#ff5252")
        else:
            self.info_label.config(text=f"Atlas Size: {total_size}x{total_size}", fg="#4caf50")

        self.full_atlas_preview = Image.new("RGBA", (total_size, total_size), (30, 30, 30, 255))
        for idx, img in enumerate(baked):
            pos = idx + 1
            x, y = (pos % gs) * res, (pos // gs) * res
            self.full_atlas_preview.paste(img, (x,y))
        self.refresh_canvas()

    def refresh_canvas(self):
        if not self.full_atlas_preview: return
        w, h = self.full_atlas_preview.size
        new_size = (int(w * self.zoom_level), int(h * self.zoom_level))
        mode = Image.NEAREST if self.zoom_level > 1 else Image.LANCZOS
        self.preview_tk = ImageTk.PhotoImage(self.full_atlas_preview.resize(new_size, mode))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_tk)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def generate(self):
        if not self.groups: return
        res, prfx = self.tile_res_var.get(), self.planet_var.get().lower()
        mode = self.trans_mode_var.get()
        baked_data = []
        trn_blocks = {}
        indices = sorted(self.groups.keys())
        
        for i in indices:
            trn_blocks[i] = {"solids": [], "transitions": []}

# 1. Process Solids (Updated for repeated index naming)
        for i in indices:
            vars_found = sorted(self.groups[i].keys())
            # Create the repeated index string (e.g., 0->00, 1->11, 10->1010)
            repeat_idx = f"{i}{i}" if i > 9 else f"{i}{i}" # Simplified: just repeat i
            
            for idx, var in enumerate(vars_found):
                # Using repeat_idx so Tile 1 becomes dw11sA0.MAP
                name = f"{prfx}{repeat_idx}s{var}0.MAP"
                baked_data.append((name, self.groups[i][var]))
                slot = chr(65 + idx) 
                trn_blocks[i]["solids"].append((slot, name))

        # 2. Process Transitions (Fixed Filenames)
        c_m, d_m = self.generate_mask("cap"), self.generate_mask("diag")
        for idx, i in enumerate(indices):
            if mode == "Linear":
                targets = [indices[idx + 1]] if idx + 1 < len(indices) else []
            else:
                targets = indices[idx + 1:]

            for j in targets:
                base_img = self.groups[i]["A"]
                target_img = self.groups[j]["A"]
                
                c_img = base_img.copy(); c_img.paste(target_img, (0,0), c_m)
                d_img = base_img.copy(); d_img.paste(target_img, (0,0), d_m)
                
                # Filename fix: prefix + source + target + cap/diag + variant + mip
                c_name = f"{prfx}{i}{j}cA0.MAP" 
                d_name = f"{prfx}{i}{j}dA0.MAP"
                
                baked_data.append((c_name, c_img))
                baked_data.append((d_name, d_img))
                trn_blocks[i]["transitions"].append((j, c_name, d_name))

        # 3. Atlas Construction
        gs = math.ceil(math.sqrt(len(baked_data) + 1))
        at_res = gs * res 
        at_img = Image.new("RGBA", (at_res, at_res), (128, 128, 128, 255))
        uv = res / at_res
        csv_lines = [f",0.000,0.000,{uv:.3f},{uv:.3f}"]
        
        for idx, (name, img) in enumerate(baked_data):
            pos = idx + 1
            x, y = (pos % gs) * res, (pos // gs) * res
            at_img.paste(img, (x, y))
            csv_lines.append(f"{name},{x/at_res:.3f},{y/at_res:.3f},{uv:.3f},{uv:.3f}")
        
        # 4. Export
        if self.exp_png.get(): at_img.save(f"{prfx}_ATLAS_D.png")
        if self.exp_csv.get():
            with open(f"{prfx}_ATLAS.csv", "w", newline='\r\n') as f: f.write("\n".join(csv_lines))
        if self.exp_trn.get():
            with open(f"{prfx.upper()}_CONFIG.TRN", "w") as f:
                for idx in sorted(trn_blocks.keys()):
                    f.write(f"\n[TextureType{idx}]\nFlatColor= 128\n")
                    for slot, name in trn_blocks[idx]["solids"]: 
                        f.write(f"Solid{slot}0 = {name}\n")
                    for target, c_n, d_n in trn_blocks[idx]["transitions"]:
                        f.write(f"CapTo{target}_A0 = {c_n}\nDiagonalTo{target}_A0 = {d_n}\n")
                        
        messagebox.showinfo("Export Done", f"Bundle generated at {at_res}x{at_res}!")

if __name__ == "__main__":
    root = tk.Tk(); app = BZ98TRNArchitect(root); root.mainloop()