# Battlezone98Redux_WorldBuilder
A powerful world building tool that auto creates custom atlases, material files, TRN entries, cubemaps, HG2 conversion, and more

<img width="1920" height="1032" alt="image" src="https://github.com/user-attachments/assets/0b25ab7a-9b9b-43cd-8ad2-c24e5f49d70c" />

HOW TO USE THE ATLAS CREATOR

1. NAVIGATION TIPS
   - PREVIEW PAN: Click and drag with the Left Mouse Button to move the atlas preview.
   - PREVIEW ZOOM: Use the Mouse Wheel to zoom in and out of the texture tiles.
   - CONTROL PANEL: If the options on the left are cut off, use the Scroll Wheel or the 
     scrollbar on the far left edge to reveal the 'Build' button.

2. PREPARE SOURCE TEXTURES
   - Place your solid textures in a single folder.
   - Name them S0.dds (or PNG), S1.dds, S2.dds, etc. (up to S9).
   - Variations (e.g., S0_B.dds) are automatically used for randomization.

3. TRANSITION LOGIC (Quantity of Tiles)
   - LINEAR: Creates a sequence. S0 links to S1, S1 links to S2, etc. Best for biomes.
   - MATRIX: Creates every possible combination. Every S# links to every other S#.

4. PATTERN ENGINE (The 'Look')
   - STYLE: Sets the visual transition shape (e.g., 'Square/Blocky' for tech, 'Soft Clouds').
   - EDGE DEPTH: How far the transition effect reaches into the solid tiles.
   - FREQUENCY: The density of the transition pattern (Teeth per size).
   - JITTER: Adds random offset to edges for a less uniform, 'hand-painted' feel.
   - FEATHERING: Applies a blur filter to the transition mask for smoother blends.
   - NEW SEED: Randomizes the jitter and pattern noise for the current settings.

5. MAP GENERATION
   - NORMAL MAP: Creates a 'Smart' depth map using a Sobel operator on color data.
   - SPECULAR MAP: Creates high-contrast gloss mapping based on pixel luminosity.
   - EMISSIVE MAP: Isolates bright colors (threshold > 220) to create glow assets.

6. EXPORT FILES
   - CSV MAPPING: A manifest identifying which tile is which for internal tools.
   - TRN CONFIG: The terrain configuration file defining TextureTypes for the engine.
     Note: This provides the texture tile entries ready for copy/paste into a TRN.
   - MATERIAL FILE: The Ogre script linking textures to shaders and aliases.

<img width="1380" height="966" alt="image" src="https://github.com/user-attachments/assets/8b654843-9c7d-4501-9fec-71e8263bb4a8" />

1. CUBEMAP GENERATOR
   • INPUT: Requires 1 high resolution equirectangular HDRI projection image.
   • Prefix: The naming convention your textures and materials will use.
   • RESIZE: Forces all faces to matching powers of 2 (e.g., 1024px).
   • DDS CONVERSION: Automatically exports faces into DDS format.(Recommended)

2. HG2 CONVERTER
   • RAW DATA: Reads Battlezone heightfield data (.hg2) and converts it to a visual heightmap.
   • PRESETS: Match your map scale (e.g., Medium 5120m) to ensure correct aspect ratios.
     This only applies when going PNG to HG2.
   • BRIGHTNESS/CONTRAST: Adjust to expand the dynamic range of the terrain peaks/valleys.
       Try defaults first.
   • SMOOTHING: Runs a Gaussian pass to remove 'stair-stepping' on low-res terrain.

