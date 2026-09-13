import os
import tempfile
import unittest

from legacy_preflight import emit_resolved_palette, is_legacy_terrain_map_name


class LegacyPreflightTests(unittest.TestCase):
    def test_emits_embedded_stock_palette_requested_by_trn(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source")
            output = os.path.join(root, "output")
            os.makedirs(source)
            os.makedirs(output)
            with open(os.path.join(source, "map.trn"), "w", encoding="cp1252") as stream:
                stream.write("[Color]\nPalette=MARS.ACT\n")

            path, check = emit_resolved_palette(source, output)
            self.assertEqual(check.level, "pass")
            self.assertIsNotNone(path)
            self.assertEqual(os.path.basename(path).lower(), "mars.act")
            self.assertEqual(os.path.getsize(path), 768)

    def test_terrain_map_filter_only_matches_atlas_tiles(self):
        self.assertTrue(is_legacy_terrain_map_name("EG00SA0.MAP"))
        self.assertTrue(is_legacy_terrain_map_name("mg12dc3.map"))
        self.assertFalse(is_legacy_terrain_map_name("BLUSKY.MAP"))
        self.assertFalse(is_legacy_terrain_map_name("custom.map"))


if __name__ == "__main__":
    unittest.main()
