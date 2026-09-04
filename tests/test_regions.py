import unittest

from acc_sdk import ApsRegion, normalize_aps_region


class TestApsRegions(unittest.TestCase):
    def test_exposes_all_current_autodesk_region_values(self):
        self.assertEqual(
            [region.value for region in ApsRegion],
            ["US", "EMEA", "AUS", "CAN", "DEU", "IND", "JPN", "GBR"],
        )

    def test_defaults_to_us(self):
        self.assertIs(normalize_aps_region(), ApsRegion.US)
        self.assertEqual(str(normalize_aps_region()), "US")

    def test_normalizes_string_case_and_whitespace(self):
        self.assertIs(normalize_aps_region(" us "), ApsRegion.US)
        self.assertIs(normalize_aps_region("aus"), ApsRegion.AUS)

    def test_preserves_enum_members_and_accepts_explicit_default(self):
        self.assertIs(normalize_aps_region(ApsRegion.CAN), ApsRegion.CAN)
        self.assertIs(
            normalize_aps_region(default=ApsRegion.EMEA), ApsRegion.EMEA
        )

    def test_rejects_deprecated_or_invalid_region_values(self):
        for value in ("APAC", "EU", "", "moon", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_aps_region(value)

    def test_validates_custom_default(self):
        with self.assertRaises(ValueError):
            normalize_aps_region(default="APAC")


if __name__ == "__main__":
    unittest.main()
