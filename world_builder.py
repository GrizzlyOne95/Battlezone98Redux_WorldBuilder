import os
import sys
import ctypes
import math
import threading
import random
import re
import numpy as np
import struct
import imageio
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageDraw, ImageFilter, ImageTk, ImageOps, ImageEnhance
from scipy.ndimage import map_coordinates

# --- BATTLEZONE HUD COLORS ---
BZ_BG = "#0a0a0a"
BZ_FG = "#d4d4d4"
BZ_GREEN = "#00ff00"
BZ_DARK_GREEN = "#004400"
BZ_CYAN = "#00ffff"

class BZ98TRNArchitect:
    def __init__(self, root):
        self.root = root # Keep reference to main root
        self.root.title("BZ98 Redux: World Builder Suite")
        self.root.geometry("1400x950")
        self.root.configure(bg=BZ_BG)
        
        # Initialize variables first to prevent AttributeErrors
        self.sky_prefix_var = tk.StringVar(value="pmars")
        self.hg2_path = tk.StringVar() 
        
# Use self. to make it an instance attribute
        self.map_presets = [
            "Tiny (1280m)", "Small (2560m)", "Medium (5120m)", 
            "Large (10240m)", "Huge (20480m)", "Custom"
        ]
        
        self.selected_preset = tk.StringVar(value=self.map_presets[2]) # Defaults to Medium
        
        self.hg2_width_meters = tk.IntVar(value=5120)
        self.hg2_depth_meters = tk.IntVar(value=5120)

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
        self.sky_out_res = tk.IntVar(value=2048)
        self.zoom_level = 0.25
        self.trans_mode_var = tk.StringVar(value="Linear")
        self.trans_mode_var.trace_add("write", self.update_preview)
        self.trans_mode_var.trace_add("write", lambda *args: self.update_preview())
        self.style_var.trace_add("write", lambda *args: self.update_preview())
        
        self.export_dds = tk.BooleanVar(value=True)
        self.export_mat = tk.BooleanVar(value=True)
        self.export_trn = tk.BooleanVar(value=True)
        
        # HG2 Conversion Control Variables
        self.hg2_target_zw = tk.IntVar(value=8) # Default 8 zones wide
        self.hg2_target_zl = tk.IntVar(value=8) # Default 8 zones long
        self.hg2_brightness = tk.DoubleVar(value=1.0)
        self.hg2_contrast = tk.DoubleVar(value=1.0)
        self.hg2_smooth_val = tk.IntVar(value=0)

        # Export Toggles
        self.exp_png = tk.BooleanVar(value=False)
        self.exp_dds = tk.BooleanVar(value=True)
        self.exp_csv = tk.BooleanVar(value=True)
        self.exp_trn = tk.BooleanVar(value=True)
        self.exp_mat = tk.BooleanVar(value=True)
        self.exp_normal = tk.BooleanVar(value=False)
        self.exp_specular = tk.BooleanVar(value=False)
        self.exp_emissive = tk.BooleanVar(value=False)
        
        self.source_dir = ""
        self.groups = {} 
        self.full_atlas_preview = None
        self.preview_tk = None

        # Font/Icon logic
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
            self.resource_dir = sys._MEIPASS
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.resource_dir = self.base_dir
            
        font_path = os.path.join(self.resource_dir, "bzone.ttf")
        if os.path.exists(font_path):
            self.custom_font_name = "BZONE"
            try: ctypes.windll.gdi32.AddFontResourceExW(font_path, 0x10, 0)
            except: pass
        else:
            self.custom_font_name = "Consolas"

        icon_path = os.path.join(self.resource_dir, "modman.ico")
        if os.path.exists(icon_path):
            try: self.root.iconbitmap(icon_path)
            except: pass

        try:
            self.resample_method = Image.Resampling.LANCZOS
        except AttributeError:
            self.resample_method = Image.LANCZOS

        self.setup_styles()
        self.setup_ui()
        self.bind_events()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('default')
        main_font = (self.custom_font_name, 10)
        bold_font = (self.custom_font_name, 11, "bold")

        # --- GLOBAL STYLES ---
        style.configure(".", background=BZ_BG, foreground=BZ_FG, font=main_font, bordercolor=BZ_DARK_GREEN)
        style.configure("TFrame", background=BZ_BG)
        style.configure("TNotebook", background=BZ_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#1a1a1a", foreground=BZ_FG, padding=[10, 2])
        style.map("TNotebook.Tab", background=[("selected", BZ_DARK_GREEN)], foreground=[("selected", BZ_GREEN)])
        style.configure("TLabelframe", background=BZ_BG, bordercolor=BZ_GREEN)
        style.configure("TLabelframe.Label", background=BZ_BG, foreground=BZ_GREEN, font=bold_font)
        style.configure("TLabel", background=BZ_BG, foreground=BZ_FG)
        style.configure("TEntry", fieldbackground="#1a1a1a", foreground=BZ_CYAN, insertcolor=BZ_GREEN)
        style.configure("TButton", background="#1a1a1a", foreground=BZ_FG)
        style.map("TButton", background=[("active", BZ_DARK_GREEN)], foreground=[("active", BZ_GREEN)])
        style.configure("Success.TButton", foreground=BZ_GREEN, font=bold_font)
        style.configure("Action.TButton", foreground=BZ_CYAN, font=bold_font)
        style.configure("Vertical.TScrollbar", background="#1a1a1a", troughcolor=BZ_BG, arrowcolor=BZ_GREEN)
        style.configure("TCheckbutton", background=BZ_BG, foreground=BZ_FG, indicatorcolor=BZ_BG, indicatoron=True)
        style.map("TEntry", fieldbackground=[("readonly", "#1a1a1a")], foreground=[("readonly", BZ_CYAN)])
        style.configure("TCombobox", fieldbackground="#1a1a1a", foreground=BZ_CYAN, arrowcolor=BZ_GREEN)
        style.map("TCombobox", fieldbackground=[("readonly", "#1a1a1a")], foreground=[("readonly", BZ_CYAN)])
        style.configure("TMenubutton", background="#1a1a1a", foreground=BZ_CYAN)
        style.map("TMenubutton", background=[("active", BZ_DARK_GREEN)], foreground=[("active", BZ_GREEN)])
    
    def setup_help_tab(self):
        container = ttk.Frame(self.tab_help, padding=30)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="World Builder Suite Guide", font=(self.custom_font_name, 16, "bold")).pack(anchor="w", pady=(0, 20))

        # Main horizontal split
        columns_frame = ttk.Frame(container)
        columns_frame.pack(fill="both", expand=True)

        # --- COLUMN 1: ATLAS CREATOR (LEFT) ---
        left_col = ttk.Frame(columns_frame)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 20))

        ttk.Label(left_col, text="ATLAS CREATOR", font=(self.custom_font_name, 11, "bold"), foreground=BZ_GREEN).pack(anchor="w")
        help_box_left = tk.Text(left_col, font=("Consolas", 10), bg="#050505", fg=BZ_FG, relief="flat", wrap="word", insertbackground=BZ_GREEN)
        help_box_left.pack(fill="both", expand=True, pady=10)

        atlas_guide = (
            "HOW TO USE THE ATLAS CREATOR\n\n"
            "1. NAVIGATION TIPS\n"
            "   - PREVIEW PAN: Click and drag with the Left Mouse Button to move the atlas preview.\n"
            "   - PREVIEW ZOOM: Use the Mouse Wheel to zoom in and out of the texture tiles.\n"
            "   - CONTROL PANEL: If the options on the left are cut off, use the Scroll Wheel or the \n"
            "     scrollbar on the far left edge to reveal the 'Build' button.\n\n"
            "2. PREPARE SOURCE TEXTURES\n"
            "   - Place your solid textures in a single folder.\n"
            "   - Name them S0.dds (or PNG), S1.dds, S2.dds, etc. (up to S9).\n"
            "   - Variations (e.g., S0_B.dds) are automatically used for randomization.\n\n"
            "3. TRANSITION LOGIC (Quantity of Tiles)\n"
            "   - LINEAR: Creates a sequence. S0 links to S1, S1 links to S2, etc. Best for biomes.\n"
            "   - MATRIX: Creates every possible combination. Every S# links to every other S#.\n\n"
            "4. PATTERN ENGINE (The 'Look')\n"
            "   - STYLE: Sets the visual transition shape (e.g., 'Square/Blocky' for tech, 'Soft Clouds').\n"
            "   - EDGE DEPTH: How far the transition effect reaches into the solid tiles.\n"
            "   - FREQUENCY: The density of the transition pattern (Teeth per size).\n"
            "   - JITTER: Adds random offset to edges for a less uniform, 'hand-painted' feel.\n"
            "   - FEATHERING: Applies a blur filter to the transition mask for smoother blends.\n"
            "   - NEW SEED: Randomizes the jitter and pattern noise for the current settings.\n\n"
            "5. MAP GENERATION\n"
            "   - NORMAL MAP: Creates a 'Smart' depth map using a Sobel operator on color data.\n"
            "   - SPECULAR MAP: Creates high-contrast gloss mapping based on pixel luminosity.\n"
            "   - EMISSIVE MAP: Isolates bright colors (threshold > 220) to create glow assets.\n\n"
            "6. EXPORT FILES\n"
            "   - CSV MAPPING: A manifest identifying which tile is which for internal tools.\n"
            "   - TRN CONFIG: The terrain configuration file defining TextureTypes for the engine.\n"
            "     Note: This provides the texture tile entries ready for copy/paste into a TRN.\n"
            "   - MATERIAL FILE: The Ogre script linking textures to shaders and aliases."
        )
        help_box_left.insert("1.0", atlas_guide)
        help_box_left.config(state="disabled")

        # --- COLUMN 2: WORLD TOOLS (RIGHT) ---
        right_col = ttk.Frame(columns_frame)
        right_col.pack(side="right", fill="both", expand=True, padx=(20, 0))

        ttk.Label(right_col, text="WORLD BUILDER TOOLS", font=(self.custom_font_name, 11, "bold"), foreground=BZ_CYAN).pack(anchor="w")
        help_box_right = tk.Text(right_col, font=("Consolas", 10), bg="#050505", fg=BZ_FG, relief="flat", wrap="word", insertbackground=BZ_GREEN)
        help_box_right.pack(fill="both", expand=True, pady=10)

        tools_guide = (
            "1. CUBEMAP GENERATOR\n"
            "   • INPUT: Requires 1 high resolution equirectangular HDRI projection image.\n"
            "   • Prefix: The naming convention your textures and materials will use.\n"
            "   • RESIZE: Forces all faces to matching powers of 2 (e.g., 1024px).\n"
            "   • DDS CONVERSION: Automatically exports faces into DDS format.(Recommended)\n\n"
            "2. HG2 CONVERTER\n"
            "   • RAW DATA: Reads Battlezone heightfield data (.hg2) and converts it to a visual heightmap.\n"
            "   • PRESETS: Match your map scale (e.g., Medium 5120m) to ensure correct aspect ratios.\n     This only applies when going PNG to HG2.\n"
            "   • BRIGHTNESS/CONTRAST: Adjust to expand the dynamic range of the terrain peaks/valleys.\n       Try defaults first.\n"
            "   • SMOOTHING: Runs a Gaussian pass to remove 'stair-stepping' on low-res terrain.\n\n"
        )
        help_box_right.insert("1.0", tools_guide)
        help_box_right.config(state="disabled")

        # Footer
        ttk.Label(container, text="BZ98R World Builder | Developed by GrizzlyOne95", 
                 font=(self.custom_font_name, 8, "italic"), foreground="#666666").pack(side="bottom", anchor="w")
    
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
            # Trigger preview update after selection
            self.update_hg2_preview()

    def convert_hg2_to_png(self):
        path = self.hg2_path.get()
        if not path or not os.path.exists(path):
            return
        
        self.btn_hg2_png.config(text="CONVERTING...", state="disabled")
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
                self.root.after(0, lambda: messagebox.showinfo("Success", f"Converted & Rotated 90° CCW\nRes: {out_img.width}x{out_img.height}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Conversion failed: {e}"))
        finally:
            self.root.after(0, lambda: self.btn_hg2_png.config(text="HG2 -> PNG", state="normal"))

    def convert_png_to_hg2(self):
        path = self.hg2_path.get()
        if not path or not os.path.exists(path): return
        
        cfg = {
            "path": path,
            "zw": getattr(self, 'hg2_target_zw', tk.IntVar(value=8)).get(),
            "zl": getattr(self, 'hg2_target_zl', tk.IntVar(value=8)).get(),
            "brightness": self.hg2_brightness.get() if hasattr(self, 'hg2_brightness') else 1.0,
            "contrast": self.hg2_contrast.get() if hasattr(self, 'hg2_contrast') else 1.0,
            "smooth": self.hg2_smooth_val.get() if hasattr(self, 'hg2_smooth_val') else 0
        }
        self.btn_png_hg2.config(text="CONVERTING...", state="disabled")
        threading.Thread(target=self._convert_png_to_hg2_worker, args=(cfg,), daemon=True).start()

    def _convert_png_to_hg2_worker(self, cfg):
        try:
            # 1. Load the 16-bit PNG
            img = Image.open(cfg["path"]).convert("I;16")
            
            # 2. Dynamic Dimensions Calculation
            z_w = cfg["zw"]
            z_l = cfg["zl"]
            
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
            arr *= cfg["brightness"]
            mean = 32768.0
            arr = (arr - mean) * cfg["contrast"] + mean
            
            # Smoothing fix for Pillow mode compatibility
            if cfg["smooth"] > 0:
                img_proc = Image.fromarray((arr / 256).astype(np.uint8)).convert("RGB")
                img_proc = img_proc.filter(ImageFilter.GaussianBlur(cfg["smooth"]))
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
            
            out_path = cfg["path"].rsplit('.', 1)[0] + "_export.hg2"
            with open(out_path, "wb") as f:
                f.write(header)
                f.write(output_data)
                    
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Exported {z_w}x{z_l} HG2 (Zone Size: {zone_size})"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to save HG2: {e}"))
        finally:
            self.root.after(0, lambda: self.btn_png_hg2.config(text="PNG -> HG2", state="normal"))
        
    # --- THE MISSING METHOD ---
    def create_fine_tune_slider(self, parent, label, var, from_, to, res=1.0):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)
        ttk.Label(frame, text=label, font=(self.custom_font_name, 9)).pack(side="top", anchor="w")
        inner = ttk.Frame(frame)
        inner.pack(fill="x")
        
        def adjust(delta):
            val = var.get() + delta
            var.set(round(max(from_, min(to, val)), 3))
            self.update_preview()

        ttk.Button(inner, text="<", command=lambda: adjust(-res), width=2).pack(side="left")
        scale = tk.Scale(inner, from_=from_, to=to, resolution=res, orient="horizontal", 
                         variable=var, command=self.force_refresh, showvalue=True,
                         bg=BZ_BG, fg=BZ_FG, troughcolor="#1a1a1a", activebackground=BZ_GREEN, highlightthickness=0)
        scale.pack(side="left", fill="x", expand=True)
        ttk.Button(inner, text=">", command=lambda: adjust(res), width=2).pack(side="left")

    def setup_ui(self):
        # 1. Create Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both")

        # 2. Setup TAB 1 (Atlas Generator)
        self.tab_trn = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_trn, text=" Atlas Creator ")

        # --- TAB 1 CONTROLS ---
        left_container = ttk.Frame(self.tab_trn, width=360)
        left_container.pack(side="left", fill="y")
        left_container.pack_propagate(False) 

        canvas = tk.Canvas(left_container, highlightthickness=0, bg=BZ_BG)
        scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
        ctrls = ttk.Frame(canvas, padding=15)

        ctrls.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=ctrls, anchor="nw", width=335)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
# --- HELP BUTTON ---
        help_btn_frame = ttk.Frame(ctrls)
        help_btn_frame.pack(fill="x", pady=(0, 10))
        ttk.Button(help_btn_frame, text="❓ About / Help", 
                  command=lambda: self.notebook.select(self.tab_help)).pack(side="right")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # --- WIDGETS ---
        ttk.Label(ctrls, text="PLANET CONFIG", font=(self.custom_font_name, 11, "bold"), foreground=BZ_GREEN).pack(anchor="w")
        ttk.Entry(ctrls, textvariable=self.planet_var, width=10).pack(anchor="w", pady=2)
        
        ttk.Label(ctrls, text="DESIRED TILE SIZE:").pack(anchor="w", pady=(10,0))
        res_opts = [256, 512, 1024, 2048, 4096]
        self.res_dropdown = ttk.Combobox(ctrls, textvariable=self.tile_res_var, values=res_opts, state="readonly")
        self.res_dropdown.pack(fill="x", pady=5)

        ttk.Separator(ctrls, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(ctrls, text="PATTERN ENGINE", font=(self.custom_font_name, 11, "bold"), foreground=BZ_GREEN).pack(anchor="w")
        
        ttk.Label(ctrls, text="TRANSITION LOGIC:").pack(anchor="w", pady=(10,0))
        ttk.Combobox(ctrls, textvariable=self.trans_mode_var, values=["Linear", "Matrix"], state="readonly").pack(fill="x", pady=5)
        
        self.style_dropdown = ttk.Combobox(ctrls, textvariable=self.style_var, state="readonly")
        self.style_dropdown.pack(fill="x", pady=5)

        self.create_fine_tune_slider(ctrls, "Edge Depth:", self.depth_var, 0.0, 0.5, 0.01)
        self.create_fine_tune_slider(ctrls, "Frequency (Teeth/Size):", self.teeth_count, 2, 80, 1)
        self.create_fine_tune_slider(ctrls, "Random Jitter:", self.jitter_var, 0.0, 50.0, 0.5)
        self.create_fine_tune_slider(ctrls, "Feathering (Blur):", self.blend_softness, 0, 50, 1)

        ttk.Button(ctrls, text="🎲 NEW SEED", command=self.cycle_seed).pack(fill="x", pady=5)
        self.info_label = ttk.Label(ctrls, text="Atlas Size: 0x0", foreground="#666666")
        self.info_label.pack(fill="x", pady=5)

        ttk.Separator(ctrls, orient="horizontal").pack(fill="x", pady=15)

        # Output Settings
        ttk.Label(ctrls, text="OUTPUT OPTIONS", font=(self.custom_font_name, 10, "bold"), foreground=BZ_GREEN).pack(anchor="w")
        for text, var in [
            ("Export PNG (Preview)", self.exp_png),
            ("Export DDS (Production)", self.exp_dds),
            ("Export Normal Map", self.exp_normal),
            ("Export Specular Map", self.exp_specular),
            ("Export Emissive Map", self.exp_emissive),
            ("Export CSV Mapping", self.exp_csv),
            ("Export .TRN Config", self.exp_trn),
            ("Export .material File", self.exp_mat)
        ]:
            ttk.Checkbutton(ctrls, text=text, variable=var).pack(anchor="w")

        ttk.Separator(ctrls, orient="horizontal").pack(fill="x", pady=15)

        # 1. SOURCE SELECT
        ttk.Button(ctrls, text="1. SELECT SOURCE FOLDER", command=self.browse).pack(fill="x", pady=(0,5))
        
        # 2. OUTPUT SELECT (NEW)
        ttk.Label(ctrls, text="OUTPUT DESTINATION:", font=(self.custom_font_name, 8, "bold")).pack(anchor="w")
        out_f = ttk.Frame(ctrls)
        out_f.pack(fill="x", pady=2)
        self.out_dir_var = tk.StringVar(value="Export")
        ttk.Entry(out_f, textvariable=self.out_dir_var, font=(self.custom_font_name, 8)).pack(side="left", fill="x", expand=True)
        ttk.Button(out_f, text="...", command=self.browse_output, width=3).pack(side="left", padx=2)

        self.btn_generate = ttk.Button(ctrls, text="2. BUILD ATLAS", command=self.generate, style="Success.TButton")
        self.btn_generate.pack(fill="x", pady=(15, 20))

        # --- TAB 1 PREVIEW ---
        pre_frame = ttk.Frame(self.tab_trn)
        pre_frame.pack(side="right", expand=True, fill="both")
        self.canvas = tk.Canvas(pre_frame, bg="#050505", highlightthickness=0)
        self.canvas.pack(side="left", expand=True, fill="both")
        # --- WORLD BUILDER TOOLS TAB
        self.tab_world = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_world, text=" World Builder Tools ")
        self.setup_world_tab()
        self.on_mode_change()
        
        # 4. Setup TAB 3 (Help)
        self.tab_help = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_help, text=" Help & About ")
        self.setup_help_tab()

    def browse_output(self):
        d = filedialog.askdirectory()
        if d: self.out_dir_var.set(d)
        
    def generate_normal_map(self, image, strength=1.0):
        """Converts a grayscale heightmap version of the atlas into a Tangent Space Normal Map."""
        gray = ImageOps.grayscale(image)
        arr = np.array(gray).astype(np.float32)
        
        # Sobel Operators
        dx = np.zeros_like(arr)
        dy = np.zeros_like(arr)
        dx[:, 1:-1] = (arr[:, 2:] - arr[:, :-2]) * strength
        dy[1:-1, :] = (arr[2:, :] - arr[:-2, :]) * strength
        
        # Normalize to 0-255 range for RGB (Normal maps use 128,128,255 as flat)
        mag = np.sqrt(dx**2 + dy**2 + 100.0**2)
        nx = (dx / mag) * 127.5 + 127.5
        ny = (dy / mag) * 127.5 + 127.5
        nz = (100.0 / mag) * 127.5 + 127.5
        
        norm_arr = np.stack([nx, ny, nz], axis=-1).astype(np.uint8)
        return Image.fromarray(norm_arr)

    def generate_specular_map(self, image):
        """Generates a Specular/Roughness map based on luminosity and contrast."""
        # Convert to grayscale and increase contrast to separate shiny/matte areas
        spec = ImageOps.grayscale(image)
        enhancer = ImageEnhance.Contrast(spec)
        spec = enhancer.enhance(1.5) 
        return spec

    def setup_world_tab(self):
        container = ttk.Frame(self.tab_world, padding=20)
        container.pack(fill="both", expand=True)

        # --- LEFT PANEL: CONTROLS ---
        left_panel = ttk.Frame(container, width=400) 
        left_panel.pack(side="left", fill="y", padx=(0, 20))
        left_panel.pack_propagate(False) 

        # --- SECTION 1: SKYBOX TOOLS ---
        ttk.Label(left_panel, text="SKYBOX TOOLS", font=(self.custom_font_name, 14, "bold"), foreground=BZ_GREEN).pack(anchor="w")
        
        sky_input_frame = ttk.LabelFrame(left_panel, text=" Input Panorama ", padding=10)
        sky_input_frame.pack(fill="x", pady=5)
        ttk.Entry(sky_input_frame, textvariable=self.sky_input_path).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(sky_input_frame, text="Browse", command=self.browse_skybox_image).pack(side="left")

        sky_cfg_frame = ttk.Frame(left_panel)
        sky_cfg_frame.pack(fill="x", pady=5)
        ttk.Label(sky_cfg_frame, text="Prefix:").pack(side="left")
        ttk.Entry(sky_cfg_frame, textvariable=self.sky_prefix_var, width=8).pack(side="left", padx=5)
        ttk.Label(sky_cfg_frame, text="Res:").pack(side="left", padx=(10, 0))
        ttk.OptionMenu(sky_cfg_frame, self.sky_out_res, self.sky_out_res.get(), 512, 1024, 2048).pack(side="left")

        # Skybox Export Toggles (Restored)
        sky_exp_opts = ttk.Frame(left_panel)
        sky_exp_opts.pack(fill="x", pady=5)
        ttk.Checkbutton(sky_exp_opts, text="DDS", variable=self.export_dds).pack(side="left")
        ttk.Checkbutton(sky_exp_opts, text="Material", variable=self.export_mat).pack(side="left")
        ttk.Checkbutton(sky_exp_opts, text="TRN", variable=self.export_trn).pack(side="left")

        self.btn_skybox = ttk.Button(left_panel, text="🚀 EXPORT SKYBOX", command=self.export_skybox, 
                  style="Success.TButton")
        self.btn_skybox.pack(fill="x", pady=(5, 15))

        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=10)

# --- UPDATED SECTION 2: HEIGHTMAP CONVERTER ---
        ttk.Label(left_panel, text="HEIGHTMAP CONVERTER", font=(self.custom_font_name, 14, "bold"), foreground=BZ_GREEN).pack(anchor="w")
        hg2_frame = ttk.LabelFrame(left_panel, text=" Terrain Settings ", padding=10)
        hg2_frame.pack(fill="x", pady=5)

        ttk.Entry(hg2_frame, textvariable=self.hg2_path).pack(fill="x", pady=2)
        ttk.Button(hg2_frame, text="Browse HG2/PNG", command=self.browse_hg2).pack(fill="x", pady=5)

        # Map Dimension Presets
        ttk.Label(hg2_frame, text="Map Size Preset When Converting PNG to HG2:").pack(anchor="w", pady=(5,0))
        self.preset_var = tk.StringVar(value="Medium (5120m)")
        preset_menu = ttk.Combobox(hg2_frame, textvariable=self.preset_var, values=self.map_presets, state="readonly")
        preset_menu.pack(fill="x", pady=5)
        preset_menu.bind("<<ComboboxSelected>>", self.apply_map_preset)

        # Manual Dimension Controls
        dim_frame = ttk.Frame(hg2_frame)
        dim_frame.pack(fill="x", pady=5)
        
        ttk.Label(dim_frame, text="Width (m):").grid(row=0, column=0, sticky="w")
        ttk.Entry(dim_frame, textvariable=self.hg2_width_meters, width=8).grid(row=0, column=1, padx=5)
        
        ttk.Label(dim_frame, text="Depth (m):").grid(row=1, column=0, sticky="w")
        ttk.Entry(dim_frame, textvariable=self.hg2_depth_meters, width=8).grid(row=1, column=1, padx=5)
        
        ttk.Label(hg2_frame, text="*Must be multiples of 1280", font=(self.custom_font_name, 7, "italic"), foreground="#666666").pack(anchor="w")

        self.create_hg2_slider(hg2_frame, "Brightness:", self.hg2_brightness, 0.1, 2.0, 0.1)
        self.create_hg2_slider(hg2_frame, "Contrast:", self.hg2_contrast, 0.1, 2.0, 0.1)
        self.create_hg2_slider(hg2_frame, "Smoothing:", self.hg2_smooth_val, 0, 10, 1)

        hg2_btn_frame = ttk.Frame(hg2_frame)
        hg2_btn_frame.pack(fill="x", pady=5)
        self.btn_hg2_png = ttk.Button(hg2_btn_frame, text="HG2 -> PNG", style="Action.TButton",
                  command=self.convert_hg2_to_png)
        self.btn_hg2_png.pack(side="left", expand=True, fill="x", padx=(0,2))
        self.btn_png_hg2 = ttk.Button(hg2_btn_frame, text="PNG -> HG2", style="Action.TButton",
                  command=self.convert_png_to_hg2)
        self.btn_png_hg2.pack(side="left", expand=True, fill="x", padx=(2,0))

        # --- RIGHT PANEL: UNIFIED PREVIEW ---
        right_panel = ttk.LabelFrame(container, text=" Preview Visualizer ")
        right_panel.pack(side="right", expand=True, fill="both")

        self.world_preview_canvas = tk.Canvas(right_panel, bg="#050505", highlightthickness=0)
        self.world_preview_canvas.pack(expand=True, fill="both", padx=10, pady=10)
    def apply_map_preset(self, event=None):
            selection = self.preset_var.get()
            if "Custom" in selection: return
            
            # Extract the number from the string e.g. "Small (2560m)" -> 2560
            import re
            match = re.search(r'\((\d+)m\)', selection)
            if match:
                size = int(match.group(1))
                self.hg2_width_meters.set(size)
                self.hg2_depth_meters.set(size)
    def create_hg2_slider(self, parent, label, var, from_, to, res):
        """Helper to create sliders that trigger the preview update"""
        ttk.Label(parent, text=label, font=(self.custom_font_name, 9)).pack(anchor="w")
        s = tk.Scale(parent, from_=from_, to=to, resolution=res, orient="horizontal", 
                     variable=var, command=self.update_hg2_preview,
                     bg=BZ_BG, fg=BZ_FG, troughcolor="#1a1a1a", activebackground=BZ_GREEN, highlightthickness=0)
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
            
            cw = self.world_preview_canvas.winfo_width()
            ch = self.world_preview_canvas.winfo_height()
            if cw < 10: cw, ch = 600, 600
            
            preview_8bit.thumbnail((cw, ch), self.resample_method)
            self.hg2_tk_photo = ImageTk.PhotoImage(preview_8bit)
            self.world_preview_canvas.delete("all")
            self.world_preview_canvas.create_image(cw//2, ch//2, image=self.hg2_tk_photo)
            
        except Exception as e:
            print(f"Preview Update Error: {e}")

    def bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_drag_end)
        self.canvas.bind("<MouseWheel>", self.zoom_wheel)
        self.canvas.bind("<Button-4>", self.zoom_wheel)
        self.canvas.bind("<Button-5>", self.zoom_wheel)

    def on_drag_start(self, event):
        self.canvas.config(cursor="fleur")
        self.canvas.scan_mark(event.x, event.y)

    def on_drag_motion(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_drag_end(self, event):
        self.canvas.config(cursor="")
        
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
        path = self.sky_input_path.get()
        if not path or not hasattr(self, 'generated_faces'):
            messagebox.showwarning("Warning", "Please load an image first.")
            return

        out_dir = filedialog.askdirectory(title="Select Export Folder")
        if not out_dir: return

        cfg = {
            "path": path,
            "out_dir": out_dir,
            "res": self.sky_out_res.get(),
            "prefix": self.sky_prefix_var.get().lower().strip(),
            "exp_mat": self.export_mat.get(),
            "exp_trn": self.export_trn.get()
        }
        self.btn_skybox.config(text="GENERATING CUBEMAP...", state="disabled")
        threading.Thread(target=self._export_skybox_worker, args=(cfg,), daemon=True).start()

    def _export_skybox_worker(self, cfg):
        """High-quality export with sorted TRN entries and uppercase material names."""
        try:
            # Load original for high-res processing
            img_data = np.array(Image.open(cfg["path"]).convert("RGB")).astype(np.float32)
            res = cfg["res"]
            
            # Use the user-defined prefix (enforce lowercase for filenames)
            base_name = cfg["prefix"]
            
            # Mapping faces to their specific BZ98 TRN parameters
            # Format: suffix: (Azimuth, Elevation, Roll, StarIndex)
            face_params = {
                'nz': (0, 0, 180, "01"),
                'ny': (0, -90, 0, "02"),
                'nx': (270, 0, 180, "03"),
                'pz': (180, 0, 180, "04"),
                'px': (90, 0, 180, "05"),
                'py': (0, 90, 0, "06")
            }
            
            # Map face_idx to suffixes for image generation logic
            face_map = {0: 'pz', 1: 'nz', 2: 'px', 3: 'nx', 4: 'py', 5: 'ny'}

            # 1. Generate and Save Images and .material files
            for i in range(6):
                face_arr = self.generate_cube_face(img_data, i, res, order=3)
                face_arr = np.clip(face_arr, 0, 255).astype(np.uint8)
                suffix = face_map[i]
                img = Image.fromarray(face_arr)
                
                # Save PNG
                img.save(os.path.join(cfg["out_dir"], f"{base_name}{suffix}.png"))

                # 2. Export .material file
                if cfg["exp_mat"]:
                    mat_filename = f"{base_name}{suffix}.material"
                    with open(os.path.join(cfg["out_dir"], mat_filename), "w") as f:
                        # Material name example: PMARSNZ.MAP (Uppercase)
                        mat_name_upper = f"{base_name.upper()}{suffix.upper()}.MAP"
                        f.write(f"material {mat_name_upper}\n")
                        f.write("{\n    technique\n    {\n        pass\n        {\n")
                        f.write("            vertex_program_ref Sky_vertex\n            {\n            }\n")
                        f.write("            fragment_program_ref Sky_fragment\n            {\n            }\n\n")
                        f.write("            lighting off\n            fog_override true none\n")
                        f.write("            scene_blend alpha_blend\n            depth_write off\n")
                        f.write("            texture_unit\n            {\n")
                        f.write(f"                texture {base_name}{suffix}.dds\n")
                        f.write("            }\n        }\n    }\n}\n")

            # 3. Export TRN Entry (Sorted 01 -> 06)
            if cfg["exp_trn"]:
                with open(os.path.join(cfg["out_dir"], "TRN_Entries.txt"), "w") as f:
                    f.write("[Sky]\n\nBackdropTexture =\n\nBackdropDistance= 400\n\n")
                    f.write("BackdropWidth   = 800\n\nBackdropHeight  = 100\n\n[Stars]\n\nRadius      = 4096\n\n")
                    
                    # Sort by the StarIndex ("01", "02", etc.)
                    sorted_items = sorted(face_params.items(), key=lambda x: x[1][3])
                    
                    for suffix, (azi, elev, roll, idx) in sorted_items:
                        f.write(f"Texture{idx}   = {base_name}{suffix}.map\n")
                        f.write(f"Color{idx}     = \"255 255 255 96\"\n")
                        f.write(f"Alpha{idx}     = 0\n")
                        f.write(f"Size{idx}      = 8192\n")
                        f.write(f"Azimuth{idx}   = {azi}\n")
                        f.write(f"Elevation{idx} = {elev}\n")
                        f.write(f"Roll{idx}      = {roll}\n\n")

            self.root.after(0, lambda: messagebox.showinfo("Success", "Export Complete: TRN entries sorted 01-06."))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Export Error", str(e)))
        finally:
            self.root.after(0, lambda: self.btn_skybox.config(text="🚀 EXPORT SKYBOX", state="normal"))

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
        # Create a 4x3 grid layout for the preview
        res = next(iter(face_dict.values())).width 
        canvas_img = Image.new("RGB", (res * 4, res * 3), (30, 30, 30))

        # BZ98 Star Layout Mapping
        layout = {
            'nx': (0, 1), 'pz': (1, 1), 'px': (2, 1), 'nz': (3, 1),
            'py': (1, 0), 'ny': (1, 2)
        }

        for face, (grid_x, grid_y) in layout.items():
            if face in face_dict:
                canvas_img.paste(face_dict[face], (grid_x * res, grid_y * res))

        # Update the canvas
        self.root.update_idletasks()
        cw = self.world_preview_canvas.winfo_width()
        ch = self.world_preview_canvas.winfo_height()
        if cw < 10: cw, ch = 800, 600
        
        canvas_img.thumbnail((cw, ch), self.resample_method)
        self.world_tk_photo = ImageTk.PhotoImage(canvas_img)
        
        self.world_preview_canvas.delete("all")
        self.world_preview_canvas.create_image(cw//2, ch//2, anchor="center", image=self.world_tk_photo)

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

    def generate_mask(self, mode="diag", cfg=None):
        if cfg:
            res = cfg["res"]
            style = cfg["style"]
            random.seed(cfg["seed"])
            depth_v = cfg["depth"]
            teeth_v = cfg["teeth"]
            jitter_v = cfg["jitter"]
            soft_v = cfg["softness"]
        else:
            res = self.tile_res_var.get()
            style = self.style_var.get()
            random.seed(self.seed_var.get()) 
            depth_v = self.depth_var.get()
            teeth_v = self.teeth_count.get()
            jitter_v = self.jitter_var.get()
            soft_v = self.blend_softness.get()
        
        # --- ENGINE A: VERTEX-BASED (Geometric) ---
        vertex_styles = ["Square/Blocky", "Sawtooth", "Interlocking L", "Sine Wave", "Stairs/Steps"]
        
        if style in vertex_styles:
            mask = Image.new("L", (res, res), 0)
            draw = ImageDraw.Draw(mask)
            depth_px = res * depth_v
            count = max(1, teeth_v)
            jitter = jitter_v

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
                    s_val = math.sin(t * math.pi * 2) * depth_px
                    pts.append((px + s_val, py + s_val))
                elif style == "Stairs/Steps":
                    pts.append((px, py + off))
                    pts.append((px + (res/count), py + off))
                else: # Interlocking L
                    pts.append((px, py + off))
            
            pts.append(line_end)
            draw.polygon(pts + fill_pts, fill=255)

        # --- ENGINE B: FIELD-BASED (Organic/Noise/Circuit) ---
        else:
            gradient = np.zeros((res, res), dtype=np.float32)
            for y in range(res):
                for x in range(res):
                    if style == "Radial/Impact":
                        dist = math.sqrt((res-x)**2 + (res-y)**2)
                        gradient[y, x] = dist / (res * 1.414)
                    elif mode == "cap":
                        gradient[y, x] = (y / res)
                    else:
                        gradient[y, x] = ((x + y) / (res * 2))
            
            influence = jitter_v / 100.0
            freq = max(1, teeth_v)
            
            # Generate primary noise
            noise_img = Image.effect_noise((res, res), freq)
            noise_arr = np.array(noise_img).astype(np.float32) / 255.0
            
            if style == "Voronoi/Cells":
                # Create cellular stepping
                noise_arr = np.round(noise_arr * (freq / 5)) / (freq / 5)
            
            elif style == "Plasma/Circuit":
                # FIXED: Apply aggressive sine warping to create "traces"
                # This uses the 'depth' slider (influence) to control trace complexity
                plasma = np.sin(noise_arr * freq) * np.cos(noise_arr.T * freq)
                noise_arr = (plasma + 1) / 2 # Re-normalize to 0.0 - 1.0

            # Blend noise with the directional gradient
            warped = np.clip(gradient + (noise_arr - 0.5) * influence * 2, 0, 1)
            mask = Image.fromarray((warped * 255).astype(np.uint8))
            
            # Apply final style-specific thresholding
            if style == "Soft Clouds":
                mask = mask.point(lambda p: 255 if p > 128 else 0)
            elif style == "Fractal Noise":
                mask = mask.point(lambda p: 255 if p > 128 else 0)
                crunch = Image.effect_noise((res, res), res // 4).point(lambda p: 255 if p > 220 else 0)
                mask = Image.composite(crunch, mask, mask.filter(ImageFilter.GaussianBlur(10)))
            elif style == "Binary Dither":
                mask = mask.convert("1").convert("L")
            elif style == "Plasma/Circuit":
                # Create sharp "trace" lines by thresholding the peaks of the sine waves
                mask = mask.point(lambda p: 255 if 110 < p < 145 else 0)
            else: 
                # Default sharp threshold for Voronoi and Radial
                mask = mask.point(lambda p: 255 if p > 128 else 0)

        blur = soft_v
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
                    img = Image.open(os.path.join(self.source_dir, f)).convert("RGBA").resize((res, res), self.resample_method)
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
            self.info_label.config(text=f"CRITICAL: {total_size}px (Exceeds 8k!)", foreground="#ff5252")
        else:
            self.info_label.config(text=f"Atlas Size: {total_size}x{total_size}", foreground="#4caf50")

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
        mode = Image.NEAREST
        self.preview_tk = ImageTk.PhotoImage(self.full_atlas_preview.resize(new_size, mode))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_tk)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def generate(self):
        if not self.groups: return
        cfg = {
            "res": self.tile_res_var.get(),
            "prfx": self.planet_var.get().lower(),
            "mode": self.trans_mode_var.get(),
            "out_dir": self.out_dir_var.get(),
            "exp_dds": self.exp_dds.get(),
            "exp_png": self.exp_png.get(),
            "exp_normal": self.exp_normal.get(),
            "exp_specular": self.exp_specular.get(),
            "exp_emissive": self.exp_emissive.get(),
            "exp_csv": self.exp_csv.get(),
            "exp_trn": self.exp_trn.get(),
            "exp_mat": self.exp_mat.get(),
            "style": self.style_var.get(),
            "seed": self.seed_var.get(),
            "depth": self.depth_var.get(),
            "teeth": self.teeth_count.get(),
            "jitter": self.jitter_var.get(),
            "softness": self.blend_softness.get(),
            "groups": self.groups 
        }
        self.btn_generate.config(text="BUILDING ATLAS...", state="disabled")
        threading.Thread(target=self._generate_worker, args=(cfg,), daemon=True).start()

    def _generate_worker(self, cfg):
        try:
            res = cfg["res"]
            prfx = cfg["prfx"]
            prfx_upper = prfx.upper()
            mode = cfg["mode"]
            
            baked_data = []
            trn_blocks = {}
            indices = sorted(cfg["groups"].keys())
            
            # Initialize TRN structure
            for i in indices:
                trn_blocks[i] = {"solids": [], "transitions": []}

            # 1. Process Solids
            for i in indices:
                vars_found = sorted(cfg["groups"][i].keys())
                repeat_idx = f"{i}{i}"
                for idx, var in enumerate(vars_found):
                    # Using upper case for MAP names to ensure engine compatibility
                    name = f"{prfx}{repeat_idx}s{var}0.MAP".upper()
                    baked_data.append((name, cfg["groups"][i][var]))
                    slot = chr(65 + idx) 
                    trn_blocks[i]["solids"].append((slot, name))

            # 2. Process Transitions
            c_m, d_m = self.generate_mask("cap", cfg), self.generate_mask("diag", cfg)
            for idx, i in enumerate(indices):
                # Determine logic based on Linear or Matrix mode
                targets = [indices[idx + 1]] if mode == "Linear" and idx + 1 < len(indices) else indices[idx + 1:] if mode == "Matrix" else []

                for j in targets:
                    base_img, target_img = cfg["groups"][i]["A"], cfg["groups"][j]["A"]
                    
                    # Composite the Cap
                    c_img = base_img.copy()
                    c_img.paste(target_img, (0,0), c_m)
                    
                    # Composite the Diagonal
                    d_img = base_img.copy()
                    d_img.paste(target_img, (0,0), d_m)
                    
                    c_name = f"{prfx}{i}{j}cA0.MAP".upper()
                    d_name = f"{prfx}{i}{j}dA0.MAP".upper()
                    
                    baked_data.append((c_name, c_img))
                    baked_data.append((d_name, d_img))
                    trn_blocks[i]["transitions"].append((j, c_name, d_name))

            # 3. Atlas Construction (FIXED: Zero-index alignment)
            # Calculate grid size (gs)
            gs = math.ceil(math.sqrt(len(baked_data)))
            at_res = gs * res 
            at_img = Image.new("RGBA", (at_res, at_res), (128, 128, 128, 255))
            
            # Calculate clean UV step (e.g., 0.25 for 4x4)
            uv_step = 1.0 / gs
            
            # Stock Format: The 'null' entry at the start of the CSV
            csv_lines = [f",0,0,{uv_step:.6g},{uv_step:.6g}"]
            
            for idx, (name, img) in enumerate(baked_data):
                # Calculate grid position (Start at 0,0)
                x_idx = idx % gs
                y_idx = idx // gs
                
                x_pixel, y_pixel = x_idx * res, y_idx * res
                at_img.paste(img, (x_pixel, y_pixel))
                
                # Use .6g for clean fractional formatting like stock EU
                u = x_idx * uv_step
                v = y_idx * uv_step
                csv_lines.append(f"{name},{u:.6g},{v:.6g},{uv_step:.6g},{uv_step:.6g}")
            
    # --- 4. Final Export & Map Generation ---
            out_dir = cfg["out_dir"]
            if not os.path.exists(out_dir): os.makedirs(out_dir)

            # Export CSV
            if cfg["exp_csv"]:
                csv_path = os.path.join(out_dir, f"{prfx}_mapping.csv")
                with open(csv_path, "w") as f:
                    f.write("\n".join(csv_lines))

            def save_map_asset(img, suffix):
                base_filename = f"{prfx}_atlas_{suffix}"
                ext = ".dds" if cfg["exp_dds"] else ".png"
                
                if cfg["exp_png"]:
                    img.save(os.path.join(out_dir, base_filename + ".png"))
                
                if cfg["exp_dds"]:
                    img.save(os.path.join(out_dir, base_filename + ".dds"))
                    
                return base_filename + ext

            # Map Dictionary for Material Aliases
            maps_to_write = {"DiffuseMap": save_map_asset(at_img, "d")}

            # Normal Map
            if cfg["exp_normal"]:
                maps_to_write["NormalMap"] = save_map_asset(self.generate_normal_map(at_img), "n")

            # Specular Map
            if cfg["exp_specular"]:
                maps_to_write["SpecularMap"] = save_map_asset(self.generate_specular_map(at_img), "s")

            # Full Color Emissive Map
            if cfg["exp_emissive"]:
                # Create a mask from brightness (>220)
                mask = at_img.convert("L").point(lambda p: 255 if p > 220 else 0)
                # Create a black background the same size
                black_bg = Image.new("RGB", at_img.size, (0, 0, 0))
                # Paste original colors through the mask
                em_color = Image.composite(at_img, black_bg, mask)
                maps_to_write["EmissiveMap"] = save_map_asset(em_color, "e")
            else:
                maps_to_write["EmissiveMap"] = "black.dds"

            mat_name = f"{prfx}_detail_atlas".upper()

            # --- Material File Generation ---
            if cfg["exp_mat"]:
                mat_filename = f"{prfx}_detail_atlas"
                with open(os.path.join(out_dir, f"{mat_filename}.material"), "w") as f:
                    f.write('import * from "BZTerrainBase.material"\n\n')
                    f.write(f'material {mat_filename.upper()} : BZTerrainBase\n{{\n')
                    for alias, filename in maps_to_write.items():
                        f.write(f'\tset_texture_alias {alias} {filename}\n')
                    f.write(f'\tset_texture_alias DetailMap {prfx}_detail.dds\n')
                    f.write('\n\tset $diffuse "1 1 1"\n\tset $ambient "1 1 1"\n')
                    f.write('\tset $specular ".25 .25 .25"\n\tset $shininess "63"\n}\n')

            # --- TRN Config (FIXED: Added [Atlases] block) ---
            if cfg["exp_trn"]:
                trn_path = os.path.join(out_dir, f"{prfx_upper}_CONFIG.TRN")
                with open(trn_path, "w") as f:
                    f.write("[Atlases]\n")
                    f.write(f"MaterialName = {mat_name}\n\n")
                    
                    for idx in sorted(trn_blocks.keys()):
                        f.write(f"[TextureType{idx}]\nFlatColor= 128\n")
                        # Write Solids
                        for slot, name in trn_blocks[idx]["solids"]:
                            f.write(f"Solid{slot}0 = {name}\n")
                        # Write Transitions
                        for target, c_n, d_n in trn_blocks[idx]["transitions"]:
                            f.write(f"CapTo{target}_A0 = {c_n}\n")
                            f.write(f"DiagonalTo{target}_A0 = {d_n}\n")
                            
            self.root.after(0, lambda: messagebox.showinfo("Export Done", f"World bundle generated for {prfx_upper}!\nGrid size: {gs}x{gs}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self.btn_generate.config(text="2. BUILD ATLAS", state="normal"))

if __name__ == "__main__":
    root = tk.Tk(); app = BZ98TRNArchitect(root); root.mainloop()
