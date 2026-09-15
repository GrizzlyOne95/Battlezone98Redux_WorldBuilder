"""Write the .trn side of each build: the TextureType blocks, and for the five
new worlds a complete .trn a map can actually be built on.

A tile nothing names is dead weight, so every tile the atlas carries gets a key
here -- including the ones this rebuild added, which are marked so it is obvious
what is new against the world's current .trn.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from build2 import plan_tiles
from worlds2 import WORLDS

SLOT = "ABCD"

# Stock palette / lighting-table sets, so a new world's .trn resolves against
# the base game with nothing else installed.
COLOR = {"ccmars_detail_atlas": "MARS", "cctitan_detail_atlas": "TITAN",
         "ccearth_detail_atlas": "ACHILLES", "ccmetal_detail_atlas": "MOON",
         "cctunnel_detail_atlas": "MOON"}

HEAD = """[Size]
MinX=0
MinZ=0
Width=5120
Depth=5120
Height=0.000000

[NormalView]
Time=900
FogStart=120
FogEnd=350
FogBreak=60
VisibilityRange=350
Intensity=40
Ambient=0
FlatRange=350
ShadowLuma=0
FogDirection=1
TerrainShadowLuma=20
CarAmbient=20

[Atlases]
MaterialName = {mat}

[Sky]
SunTexture=
SkyHeight = 110
SkyTexture=
BackdropTexture =
BackdropDistance= 400
BackdropWidth   = 800
BackdropHeight  = 100

[Color]
Palette={pal}.ACT
Luma={pal}.LUM
Translucency={pal}.TBL
Alpha={pal}.ALB

[World]
MusicTrack=3

"""


def type_blocks(cfg, plan, already):
    """`already` is the set of tile names the world's .trn names today; anything
    outside it is new to that .trn, whether it came from the matrix or a fill."""
    by = {}
    for t in plan:
        by.setdefault(t["i"], []).append(t)
    out = []
    for i in sorted(by):
        src = cfg["types"][i]
        out.append("[TextureType%d]   // %s" % (i, os.path.basename(src)))
        out.append("FlatColor= 128")
        for t in sorted(by[i], key=lambda t: (t["kind"] != "s", t["j"], t["kind"], t["var"])):
            if t["var"] > len(SLOT):
                out.append("; %s.map -- variant %d, no .trn slot for it" % (t["name"], t["var"]))
                continue
            key = ("Solid%s" % SLOT[t["var"] - 1] if t["kind"] == "s" else
                   "%sTo%d_%s" % ("Cap" if t["kind"] == "c" else "Diagonal",
                                  t["j"], SLOT[t["var"] - 1]))
            mark = "" if (already is None or t["name"] in already) else "   // new"
            # all four mip keys name the mip-0 tile, which is what every .trn in
            # this mod already does -- the atlas carries the real mip chain
            for mip in range(4):
                out.append("%-18s= %s.map%s" % (key + str(mip), t["name"],
                                                mark if mip == 0 else ""))
            out.append("")
    return out


def main(out_root):
    req = json.load(open(os.path.join(HERE, "required.json")))
    for mat, cfg in WORLDS.items():
        d = os.path.join(out_root, mat)
        if not os.path.isdir(d):
            continue
        plan, grid = plan_tiles(mat, cfg, req.get(mat, []))
        body = type_blocks(cfg, plan,
                           None if cfg.get("new") else set(req.get(mat, [])))
        head = ["; TextureType entries for %s -- every tile the atlas carries." % mat,
                "; Lines marked 'new' are tiles this rebuild added; the world's current",
                "; .trn does not name them yet, and a tile nothing names never draws.",
                ";", "[Atlases]", "MaterialName = %s" % mat.upper(), ""]
        open(os.path.join(d, "TRN_Entries.txt"), "w", newline="\r\n").write(
            "\n".join(head + body) + "\n")
        if cfg.get("new"):
            name = cfg["world"].lower() + ".trn"
            txt = HEAD.format(mat=mat, pal=COLOR[mat]) + "\n".join(body) + "\n"
            open(os.path.join(d, name), "w", newline="\r\n").write(txt)
            print("wrote", os.path.join(d, name))
        print("%-24s %d type blocks" % (mat, len(cfg["types"])))


if __name__ == "__main__":
    main(sys.argv[1])
