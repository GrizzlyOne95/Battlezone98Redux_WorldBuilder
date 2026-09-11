import tempfile
import unittest
from pathlib import Path

import numpy as np

from hg2_codec import HG2Header
from mission_visualizer import (
    extract_terrain_name,
    hg2_north_up,
    hg2_world_size,
    resolve_companion_hg2,
    resolve_mission_trn,
    world_to_canvas,
)


class MissionVisualizerTests(unittest.TestCase):
    def test_hg2_world_size_uses_zone_dimensions(self):
        header = HG2Header(1, 8, 4, 3, 10)
        self.assertEqual(hg2_world_size(header), (5120.0, 3840.0))

    def test_hg2_display_is_north_up(self):
        heights = np.array([[1, 2], [3, 4]], dtype=np.uint16)
        display = hg2_north_up(heights)
        self.assertTrue(np.array_equal(display, np.array([[3, 4], [1, 2]], dtype=np.uint16)))

    def test_world_to_canvas_uses_independent_axes_and_flips_z(self):
        rect = (10.0, 20.0, 200.0, 100.0)
        self.assertEqual(
            world_to_canvas(
                100.0,
                200.0,
                min_x=100.0,
                min_z=200.0,
                world_width=2560.0,
                world_depth=1280.0,
                draw_rect=rect,
            ),
            (10.0, 120.0),
        )
        self.assertEqual(
            world_to_canvas(
                2660.0,
                1480.0,
                min_x=100.0,
                min_z=200.0,
                world_width=2560.0,
                world_depth=1280.0,
                draw_rect=rect,
            ),
            (210.0, 20.0),
        )

    def test_extract_terrain_name_from_ascii_bzn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mission.bzn"
            path.write_bytes(
                b"version [1] =\r\n2016\r\nTerrainName [1] =\r\nMARS.TRN\r\n"
            )
            self.assertEqual(extract_terrain_name(path), "MARS.TRN")

    def test_resolve_trn_prefers_terrain_name_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bzn = root / "mission.bzn"
            bzn.write_text("", encoding="ascii")
            trn = root / "ActualTerrain.TrN"
            trn.write_text("[Size]\n", encoding="ascii")
            fallback = root / "mission.trn"
            fallback.write_text("[Size]\n", encoding="ascii")
            self.assertEqual(
                resolve_mission_trn(bzn, "actualterrain.trn"),
                trn,
            )

    def test_companion_hg2_resolution_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trn = root / "terrain.trn"
            trn.write_text("", encoding="ascii")
            hg2 = root / "Terrain.HG2"
            hg2.write_bytes(b"")
            self.assertEqual(resolve_companion_hg2(trn), hg2)

    def test_binary_bzn_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mission.bzn"
            path.write_bytes(b"version [1] =\r\n2016\r\n\x00binary")
            with self.assertRaisesRegex(ValueError, "Binary BZN"):
                extract_terrain_name(path)


if __name__ == "__main__":
    unittest.main()
