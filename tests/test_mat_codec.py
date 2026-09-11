import math
import os
import tempfile
import unittest

import numpy as np

import mat_codec


class MatCodecTests(unittest.TestCase):
    def test_bitfield_known_bytes(self):
        value = mat_codec.encode_mix_entry(base=5, next_mat=2, mix=15, variant=2)
        self.assertEqual(value, 0x52F2)
        self.assertEqual(mat_codec.entry_to_bytes(value), b"\xF2\x52")
        decoded = mat_codec.decode_entry(value)
        self.assertEqual((decoded.base, decoded.next), (5, 2))
        self.assertEqual(decoded.mix, 15)
        self.assertEqual(decoded.variant, 2)
        self.assertEqual(decoded.reserved, 0)

    def test_reserved_low_nibble_is_visible_but_not_generated(self):
        decoded = mat_codec.decode_entry(0x52FE)
        self.assertEqual(decoded.variant, 2)
        self.assertEqual(decoded.reserved, 3)
        with self.assertRaises(ValueError):
            mat_codec.encode_entry(0, 0, variant=4)

    def test_zone_pack_order_and_size(self):
        grid = np.empty((128, 128), dtype=np.uint16)
        for zz in range(2):
            for xx in range(2):
                material = zz * 2 + xx
                value = mat_codec.encode_mix_entry(material, material, 0)
                grid[zz*64:(zz+1)*64, xx*64:(xx+1)*64] = value
        payload = mat_codec.pack_mat_zones(grid, 2, 2)
        self.assertEqual(len(payload), 4 * 4096 * 2)
        zone_bytes = 4096 * 2
        self.assertEqual(payload[0:2], b"\x00\x00")
        self.assertEqual(payload[zone_bytes:zone_bytes+2], b"\x00\x11")
        self.assertEqual(payload[2*zone_bytes:2*zone_bytes+2], b"\x00\x22")
        self.assertEqual(payload[3*zone_bytes:3*zone_bytes+2], b"\x00\x33")
        np.testing.assert_array_equal(mat_codec.unpack_mat_zones(payload, 2, 2), grid)

    def test_bzmapio_cap_and_diagonal_mix_mapping(self):
        entry, kind = mat_codec.encode_transition_from_corners((0, 1, 1, 0))
        self.assertEqual(kind, "cap")
        self.assertEqual(mat_codec.decode_entry(entry).mix, 6)

        entry, kind = mat_codec.encode_transition_from_corners((1, 0, 0, 0))
        self.assertEqual(kind, "diagonal")
        self.assertEqual(mat_codec.decode_entry(entry).mix, 13)

        entry, kind = mat_codec.encode_transition_from_corners((1, 0, 1, 0))
        self.assertEqual(kind, "ambiguous")
        decoded = mat_codec.decode_entry(entry)
        self.assertEqual((decoded.base, decoded.next), (0, 0))

    def test_directional_trn_transition_validation(self):
        entry, kind = mat_codec.encode_transition_from_corners(
            (1, 1, 1, 0),
            diagonal_transitions=frozenset({(0, 1)}),
        )
        self.assertEqual(kind, "unsupported")
        entry, kind = mat_codec.encode_transition_from_corners(
            (1, 1, 1, 0),
            diagonal_transitions=frozenset({(0, 1), (1, 0)}),
        )
        self.assertEqual(kind, "diagonal")
        self.assertEqual(
            (mat_codec.decode_entry(entry).base, mat_codec.decode_entry(entry).next),
            (1, 0),
        )

    def test_transition_family_is_validated_separately(self):
        entry, kind = mat_codec.encode_transition_from_corners(
            (0, 1, 1, 0),
            cap_transitions=frozenset(),
            diagonal_transitions=frozenset({(0, 1)}),
        )
        self.assertEqual(kind, "unsupported")
        entry, kind = mat_codec.encode_transition_from_corners(
            (0, 1, 1, 0),
            cap_transitions=frozenset({(0, 1)}),
            diagonal_transitions=frozenset(),
        )
        self.assertEqual(kind, "cap")

    def test_physical_slope_uses_decimeters_and_sample_spacing(self):
        row = np.arange(256, dtype=np.float32) * 10.0
        heights = np.tile(row, (256, 1))
        slope = mat_codec.calculate_slope_degrees(heights, 1, 1)
        self.assertAlmostEqual(
            float(slope[128, 128]), math.degrees(math.atan(0.2)), places=4
        )

    def test_generate_mat_is_64_by_64_per_zone(self):
        heights = np.zeros((256, 256), dtype=np.float32)
        rules = [
            {
                "mat_id": 0,
                "min_h": 0,
                "max_h": 4095,
                "min_s": 0,
                "max_s": 90,
                "mask_path": "",
            }
        ]
        grid, stats = mat_codec.generate_mat(heights, rules, 1, 1)
        self.assertEqual(grid.shape, (64, 64))
        self.assertEqual(stats.solid_tiles, 4096)
        self.assertEqual(len(mat_codec.pack_mat_zones(grid, 1, 1)), 8192)

    def test_parse_trn_layers_and_directional_transitions(self):
        text = """
[Size]
MinX=100
MinZ=200
Width=2560
Depth=1280

[Layer0]
ElevationStart=0
ElevationEnd=1000
SlopeStart=0
SlopeEnd=20
Material=0

[Layer1]
ElevationStart=1000
ElevationEnd=4095
SlopeStart=0
SlopeEnd=90
Material=3

[TextureType0]
SolidA0=x.map
CapTo3_A0=x.map
DiagonalTo3_A0=x.map

[TextureType3]
SolidA0=x.map
"""
        with tempfile.NamedTemporaryFile("w", suffix=".trn", delete=False) as handle:
            handle.write(text)
            path = handle.name
        try:
            config = mat_codec.parse_trn_painter(path)
        finally:
            os.unlink(path)
        self.assertEqual(config.texture_types, (0, 3))
        self.assertEqual(config.cap_transitions, frozenset({(0, 3)}))
        self.assertEqual(config.diagonal_transitions, frozenset({(0, 3)}))
        self.assertEqual(config.transitions, frozenset({(0, 3)}))
        self.assertEqual(len(config.layers), 2)
        self.assertEqual(config.layers[1]["mat_id"], 3)
        self.assertEqual(
            (config.min_x, config.min_z, config.width, config.depth),
            (100.0, 200.0, 2560.0, 1280.0),
        )


if __name__ == "__main__":
    unittest.main()
