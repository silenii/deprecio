"""Realistic Secondary Market Listing and Snapshot Generator for Avito."""

import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from deprecio.models.device import Device, EditionType
from deprecio.models.listing import ItemCondition, ListingBundle, MarketPlatform, SecondaryListing

CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Нижний Новгород", "Самара", "Ростов-на-Дону", "Краснодар", "Уфа",
]

EAC_KEYWORDS = ["Ростест", "РСТ", "EAC", "куплен в М.Видео", "официал", "чек есть"]
GLOBAL_KEYWORDS = ["Global", "Глобалка", "европеец", "европейская версия", "все бэнды"]
CN_KEYWORDS = ["Китаец", "CN версия", "перепрошит на оксиген", "китайская вилка", "без band 20"]
US_KEYWORDS = ["USA", "Американец", "eSIM only", "LL/A"]


class SnapshotGenerator:
    """Генератор реалистичных снапшотов объявлений Авито для аналитики вторичного рынка."""

    @classmethod
    def generate_listings(cls, device: Device, count: int = 35) -> List[SecondaryListing]:
        """Генерирует репрезентативную выборку объявлений по модели."""
        listings: List[SecondaryListing] = []

        # Базовая цена устройства (стартовая MSRP)
        base_msrp = 50000.0
        if device.editions and device.editions[0].memory_variants:
            base_msrp = device.editions[0].memory_variants[0].msrp_local

        # Расчет возраста и базового коэффициента уценки
        first_rel = None
        for ed in device.editions:
            if ed.release_date and (not first_rel or ed.release_date < first_rel):
                first_rel = ed.release_date

        months_old = 12
        if first_rel:
            today = date.today()
            months_old = max(1, (today.year - first_rel.year) * 12 + today.month - first_rel.month)

        # Кривая ориентировочной остаточной стоимости
        if months_old <= 6:
            base_rv = max(0.68, 1.0 - (months_old * 0.05))
        elif months_old <= 18:
            base_rv = max(0.50, 0.70 - ((months_old - 6) * 0.015))
        elif months_old <= 36:
            base_rv = max(0.35, 0.52 - ((months_old - 18) * 0.009))
        else:
            base_rv = max(0.20, 0.36 - ((months_old - 36) * 0.003))

        base_used_price = base_msrp * base_rv

        # Доступные версии
        editions_available = [ed.edition_type for ed in device.editions]
        if not editions_available:
            editions_available = [EditionType.EAC_ROSTEST, EditionType.GLOBAL_EU, EditionType.CN]

        for i in range(count):
            listing_id = f"avito-{device.model_id}-{1000 + i}"
            city = random.choice(CITIES)
            days_ago = random.randint(0, 30)
            pub_date = date.today() - timedelta(days=days_ago)

            # Выбор региональной версии с реалистичным распределением
            edition_type = random.choice(editions_available)
            edition_tag = ""
            edition_mult = 1.0

            if edition_type == EditionType.EAC_ROSTEST:
                edition_tag = random.choice(EAC_KEYWORDS)
                edition_mult = 1.0
            elif edition_type == EditionType.GLOBAL_EU:
                edition_tag = random.choice(GLOBAL_KEYWORDS)
                edition_mult = 0.93
            elif edition_type == EditionType.CN:
                edition_tag = random.choice(CN_KEYWORDS)
                edition_mult = 0.80
            elif edition_type == EditionType.US:
                edition_tag = random.choice(US_KEYWORDS)
                edition_mult = 0.88

            # Состояние и комплектация
            has_box = random.random() > 0.3
            has_charger = random.random() > 0.4
            has_receipt = random.random() > 0.6
            bundle = ListingBundle(
                has_original_box=has_box,
                has_original_charger=has_charger,
                has_receipt=has_receipt,
            )

            # Имитация дефектов и выбросов (5-8% объявлений)
            is_defective = i in [3, 17]
            is_outlier_fake = i == 7

            if is_defective:
                defect_phrase = "разбит экран, тач работает" if i == 3 else "на запчасти, завис на яблоке"
                title = f"{device.name} {defect_phrase}"
                desc = f"Продам {device.name}, {defect_phrase}. В остальном рабочий, самовывоз."
                price = max(500.0, round((base_used_price * 0.35) / 100) * 100)
                condition = ItemCondition.DEFECTIVE
            elif is_outlier_fake:
                title = f"{device.name} срочно"
                desc = "Цена указана за чехол! Телефон дороже, звоните."
                price = 1.0  # Фейковая заглушка '1 рубль'
                condition = ItemCondition.GOOD
            else:
                cond_choice = random.choices(
                    [ItemCondition.LIKE_NEW, ItemCondition.EXCELLENT, ItemCondition.GOOD],
                    weights=[0.25, 0.50, 0.25],
                )[0]
                cond_mult = {
                    ItemCondition.LIKE_NEW: 1.06,
                    ItemCondition.EXCELLENT: 1.0,
                    ItemCondition.GOOD: 0.92,
                }[cond_choice]

                # Вариация цены +/- 6%
                noise = random.uniform(0.94, 1.06)
                price = round((base_used_price * edition_mult * cond_mult * noise) / 100) * 100

                storage_str = "128GB"
                if device.editions and device.editions[0].memory_variants:
                    storage_str = f"{device.editions[0].memory_variants[0].storage_gb}GB"

                title = f"{device.name} {storage_str} {edition_tag}"
                desc = (
                    f"Продам {device.name}. {edition_tag}. Состояние отличное, носился в чехле и стекле. "
                    f"{'Коробка сохранилась. ' if has_box else ''}"
                    f"{'Оригинальная зарядка в комплекте. ' if has_charger else ''}"
                    f"Любые проверки на месте."
                )
                condition = cond_choice

            listings.append(
                SecondaryListing(
                    listing_id=listing_id,
                    platform=MarketPlatform.AVITO,
                    url=f"https://www.avito.ru/item/{listing_id}",
                    title=title,
                    description_text=desc,
                    price_rub=price,
                    city=city,
                    model_id=device.model_id,
                    detected_edition=edition_type if not is_defective else None,
                    condition=condition,
                    bundle=bundle,
                    published_at=pub_date,
                )
            )

        return listings

    @classmethod
    def save_snapshot(
        cls,
        device: Device,
        listings: List[SecondaryListing],
        base_dir: Optional[Path] = None,
    ) -> Path:
        """Сохраняет снапшот объявлений в формате JSON."""
        save_dir = base_dir or Path("data/snapshots")
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / f"{device.model_id}.json"

        data = [item.model_dump(mode="json") for item in listings]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return file_path

    @classmethod
    def load_snapshot(
        cls,
        model_id: str,
        base_dir: Optional[Path] = None,
    ) -> Optional[List[SecondaryListing]]:
        """Загружает существующий снапшот объявлений по model_id."""
        save_dir = base_dir or Path("data/snapshots")
        file_path = save_dir / f"{model_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [SecondaryListing(**item) for item in data]
        except Exception:
            return None

    @classmethod
    def get_or_create_snapshot(
        cls,
        device: Device,
        base_dir: Optional[Path] = None,
        count: int = 35,
    ) -> List[SecondaryListing]:
        """Возвращает существующий снапшот или создает новый при его отсутствии."""
        cached = cls.load_snapshot(device.model_id, base_dir=base_dir)
        if cached:
            return cached

        fresh = cls.generate_listings(device, count=count)
        cls.save_snapshot(device, fresh, base_dir=base_dir)
        return fresh
