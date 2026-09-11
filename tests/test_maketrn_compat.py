import unittest

import maketrn_compat


class MakeTRNCompatTests(unittest.TestCase):
    def test_dimensions_match_binary_normalization(self):
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(1280), 1280)
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(2560), 2560)
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(1281), 1280)
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(1285), 2560)
        self.assertEqual(maketrn_compat.normalize_make_trn_dimension(2000), 2560)

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


if __name__ == '__main__':
    unittest.main()
