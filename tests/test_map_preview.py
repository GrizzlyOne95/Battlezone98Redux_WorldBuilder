import os
import numpy as np
import pytest

import map_preview as mp


def test_ingame_bmp_size_is_the_shell_convention():
    # Every stock and community map that ships a preview uses exactly this.
    assert mp.INGAME_BMP_SIZE == (108, 89)


def test_parse_trn_reads_atlas_and_solids(tmp_path):
    trn = tmp_path / "demo.trn"
    trn.write_text(
        "[Size]\nWidth=2560\nDepth=2560\n\n"
        "[Atlases]\nMaterialName\t= mn_detail_atlas\n\n"
        "[TextureType0]\nSolidA0 = MN00SA0.MAP\n\n"
        "[TextureType3]\nSolidA0 = MN33SA0.MAP  // with a trailing note\n",
        newline="\r\n")
    info = mp.parse_trn(str(trn))
    assert info["material"] == "mn_detail_atlas"
    assert info["solids"] == {0: "MN00SA0.MAP", 3: "MN33SA0.MAP"}
    assert info["size"]["width"] == 2560


def test_parse_trn_survives_a_value_with_a_comment(tmp_path):
    trn = tmp_path / "c.trn"
    trn.write_text("[TextureType1]\nSolidA0 = AB11SA0.MAP // not used\n", newline="\r\n")
    assert mp.parse_trn(str(trn))["solids"] == {1: "AB11SA0.MAP"}


def test_hillshade_is_flat_for_flat_ground():
    assert mp._hillshade(np.zeros((16, 16), np.float32)) is None


def test_hillshade_centres_on_one():
    h = np.tile(np.linspace(0, 40, 32, dtype=np.float32), (32, 1))
    shade = mp._hillshade(h)
    assert shade.shape == (32, 32)
    assert 0.35 <= shade.min() and shade.max() <= 1.65


def test_downsample_area_averages_a_clean_factor():
    a = np.arange(64, dtype=np.float32).reshape(8, 8)
    out = mp._downsample(a, 4)
    assert out.shape == (4, 4)
    assert out[0, 0] == pytest.approx(a[0:2, 0:2].mean())


def test_downsample_is_identity_at_matching_size():
    a = np.zeros((5, 5), np.float32)
    assert mp._downsample(a, 5) is a
