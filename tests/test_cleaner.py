"""Unit tests for listing cleaner, defect detection, and IQR filtering (unittest)."""

import unittest
from deprecio.cleaner import ListingSanitizer, detect_defect_from_text, detect_edition_from_text
from deprecio.models.device import EditionType
from deprecio.models.listing import ItemCondition, SecondaryListing


class TestListingCleaner(unittest.TestCase):
    def test_detect_edition_from_text(self):
        self.assertEqual(
            detect_edition_from_text("Продам телефон Ростест 12/256 в идеале"),
            EditionType.EAC_ROSTEST,
        )
        self.assertEqual(
            detect_edition_from_text("Оригинальный китаец на OriginOS без бенда 20"),
            EditionType.CN,
        )
        self.assertEqual(
            detect_edition_from_text("Версия из США (LL/A) только eSim"),
            EditionType.US,
        )
        self.assertEqual(
            detect_edition_from_text("Европеец Global version"),
            EditionType.GLOBAL_EU,
        )

    def test_detect_defect_keywords(self):
        self.assertEqual(
            detect_defect_from_text("Телефон отличный, но трещина на экране"),
            "трещина на экране",
        )
        self.assertEqual(
            detect_defect_from_text("Заблокирован на icloud на запчасти"),
            "на запчасти",
        )
        self.assertIsNone(detect_defect_from_text("Полный комплект без царапин"))

    def test_sanitizer_flags_defective_listing(self):
        listing = SecondaryListing(
            listing_id="test-1",
            title="Смартфон под восстановление или на запчасти",
            price_rub=15000,
        )
        sanitized = ListingSanitizer.classify_and_filter_defects(listing)
        self.assertTrue(sanitized.is_outlier)
        self.assertEqual(sanitized.condition, ItemCondition.DEFECTIVE)
        self.assertIn("на запчасти", sanitized.outlier_reason)

    def test_sanitizer_iqr_outlier_filtering(self):
        listings = [
            SecondaryListing(listing_id="1", title="Обычный лот 1", price_rub=42000),
            SecondaryListing(listing_id="2", title="Обычный лот 2", price_rub=44000),
            SecondaryListing(listing_id="3", title="Обычный лот 3", price_rub=45000),
            SecondaryListing(listing_id="4", title="Обычный лот 4", price_rub=46000),
            SecondaryListing(listing_id="5", title="Обычный лот 5", price_rub=48000),
            SecondaryListing(listing_id="6", title="Обычный лот 6", price_rub=50000),
            SecondaryListing(listing_id="7", title="Аномально дорогой", price_rub=150000),
        ]

        valid, outliers = ListingSanitizer.filter_price_outliers_iqr(listings, iqr_multiplier=1.5)
        self.assertEqual(len(valid), 6)
        self.assertEqual(len(outliers), 1)
        self.assertEqual(outliers[0].listing_id, "7")
        self.assertIn("вне диапазона IQR", outliers[0].outlier_reason)


if __name__ == "__main__":
    unittest.main()
