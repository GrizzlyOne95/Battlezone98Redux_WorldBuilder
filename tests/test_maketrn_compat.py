import unittest

import numpy as np

import maketrn_compat


class MakeTRNCompatTests(unittest.TestCase):
    def test_dimensions_match_binary_normalization(self):
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(1280), 1280)
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(2560), 2560)
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(1281), 1280)
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(1285), 2560)
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(2000), 2560)

    def test_zero_sample_dimensions_are_rejected(self):
        for value in (1, 2, 3, 4):
            with self.assertRaises(ValueError):
                maketrn_compat.normalize_make_trn_dimension(value)

    def test_rectangular_geometry(self):
        geom = maketrn_compat.make_stock_geometry(2560, 5120)
        self.assertEqual((geom.width_meters, geom.depth_meters), (2560, 5120))
        self.assertEqual((geom.zones_x, geom.zones_z), (2, 4))

    def test_empty_elevation_uses_binary_range(self):
        self.assertEqual(maketrn_compat.validate_empty_elevation(0), 0)
        self.assertEqual(maketrn_compat.validate_empty_elevation(4094), 4094)
        with self.assertRaises(ValueError):
            maketrn_compat.validate_empty_elevation(4095)

    def test_stock_trn_height_matches_blank_create(self):
        self.assertAlmostEqual(maketrn_compat.stock_trn_height(1234), 123.4)

    def test_hgt_triangle_upsample_includes_make_trn_smoothing(self):
        source = np.array([[0, 10], [20, 40]], dtype=np.uint16)
        up = maketrn_compat.upsample_hgt_to_hg2(source)
        expected = np.array(
            [
                [9, 12, 16, 18],
                [14, 18, 23, 25],
                [22, 26, 32, 35],
                [25, 30, 37, 40],
            ],
            dtype=np.uint16,
        )
        np.testing.assert_array_equal(up, expected)

    def test_make_trn_smoothing_uses_valid_neighbors_and_half_up_rounding(self):
        source = np.array(
            [
                [0, 1, 2],
                [3, 4, 5],
                [6, 7, 8],
            ],
            dtype=np.uint16,
        )
        smoothed = maketrn_compat.smooth_make_trn_hg2(source)
        expected = np.array(
            [
                [2, 3, 3],
                [4, 4, 5],
                [5, 6, 6],
            ],
            dtype=np.uint16,
        )
        np.testing.assert_array_equal(smoothed, expected)

    def test_hgt_constant_surface_stays_constant_after_conversion(self):
        source = np.full((4, 4), 1234, dtype=np.uint16)
        up = maketrn_compat.upsample_hgt_to_hg2(source)
        self.assertEqual(up.shape, (8, 8))
        self.assertTrue(np.all(up == 1234))

    def test_hgt_zone_unpack_masks_12_bits_and_preserves_zone_order(self):
        zone_samples = maketrn_compat.HGT_SAMPLES_PER_ZONE ** 2
        left = np.full(zone_samples, 0xF123, dtype='<u2')
        right = np.full(zone_samples, 0x0456, dtype='<u2')
        raster = maketrn_compat.unpack_hgt_zones(left.tobytes() + right.tobytes(), 2, 1)
        self.assertEqual(raster.shape, (128, 256))
        self.assertTrue(np.all(raster[:, :128] == 0x0123))
        self.assertTrue(np.all(raster[:, 128:] == 0x0456))


if __name__ == '__main__':
    unittest.main()
