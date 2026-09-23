"""Parser and Normalizer for GSMArena Specifications into Deprecio Device Model."""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from deprecio.models.device import (
    BundleContents,
    Currency,
    Device,
    DeviceLineage,
    EditionType,
    ForecastProfile,
    HardwareSpecs,
    MemoryVariant,
    RegionalEdition,
)


class GSMArenaParser:
    """Конвертер сырых спецификаций GSMArena в типизированную модель Device."""

    @classmethod
    def parse_device(cls, raw: Dict[str, Any]) -> Optional[Device]:
        """Преобразует ответ GSMArena в Device."""
        if not raw:
            return None

        name = raw.get("phone_name") or raw.get("name") or "Неизвестный смартфон"
        slug = raw.get("slug") or name.lower().replace(" ", "-")
        brand = raw.get("brand") or cls._extract_brand(name)

        # Извлечение спецификаций из табличного или вложенного формата
        specs = cls._flatten_specs(raw)

        # 1. Процессор / Чипсет
        chipset = specs.get("chipset") or specs.get("platform_chipset")
        clean_chipset = cls._clean_chipset_name(chipset) if chipset else None

        # 2. Дата релиза
        release_date = cls._parse_launch_date(specs.get("announced") or specs.get("status"))

        # 3. Сеть и бэнды
        network_str = f"{specs.get('technology', '')} {specs.get('4g_bands', '')} {specs.get('5g_bands', '')}"
        has_b20 = bool(re.search(r"\b20\b", network_str))
        has_b7 = bool(re.search(r"\b7\b", network_str))
        has_b3 = bool(re.search(r"\b3\b", network_str))

        # 4. SIM и eSIM
        sim_str = specs.get("sim", "").lower()
        has_esim = "esim" in sim_str
        sim_slots = "2x NanoSIM"
        if "esim only" in sim_str:
            sim_slots = "eSIM only"
        elif "esim" in sim_str:
            sim_slots = "1x NanoSIM + eSIM"

        # 5. NFC
        nfc_str = specs.get("nfc", "").lower()
        has_nfc = "yes" in nfc_str or "да" in nfc_str or bool(nfc_str and "no" not in nfc_str)

        # 6. Зарядка и мощность
        charging_str = specs.get("charging", "") or specs.get("battery_charging", "")
        wattage = cls._extract_wattage(charging_str)

        # Наличие зарядного блока в коробке (у Apple, Samsung, Google обычно нет)
        has_charger = brand.lower() not in ["apple", "samsung", "google"] and bool(wattage)

        # 7. Конфигурации памяти
        memory_str = specs.get("internal", "") or specs.get("memory_internal", "")
        variants = cls._parse_memory_variants(memory_str)
        if not variants:
            variants = [MemoryVariant(ram_gb=8, storage_gb=256, msrp_local=69990.0, currency=Currency.RUB)]

        # 8. Сборка версий (Global / EAC)
        hardware = HardwareSpecs(
            has_band_20=has_b20,
            has_band_7=has_b7,
            has_band_3=has_b3,
            has_esim=has_esim,
            sim_slots=sim_slots,
            has_nfc=has_nfc,
        )

        bundle = BundleContents(
            has_charger=has_charger,
            charger_wattage_w=wattage,
            has_case=brand.lower() in ["xiaomi", "poco", "redmi", "realme", "honor", "vivo"],
            has_cable=True,
            has_box=True,
        )

        edition = RegionalEdition(
            edition_type=EditionType.EAC_ROSTEST if has_b20 else EditionType.CN,
            announced=True,
            release_date=release_date,
            hardware=hardware,
            bundle=bundle,
            memory_variants=variants,
        )

        # 9. Профиль уценки бренда
        profile = cls._estimate_forecast_profile(brand, name)

        return Device(
            model_id=slug,
            name=name,
            brand=brand,
            chipset=clean_chipset,
            lineage=DeviceLineage(series=cls._extract_series(name), tier=cls._estimate_tier(name)),
            editions=[edition],
            forecast_profile=profile,
        )

    @classmethod
    def _flatten_specs(cls, raw: Dict[str, Any]) -> Dict[str, str]:
        """Приводит спецификации из разных форматов к единому плоскому словарю."""
        flat: Dict[str, str] = {}
        # Если пришла таблица specs
        if "specifications_table" in raw:
            for cat, fields in raw["specifications_table"].items():
                for k, v in fields.items():
                    flat[k] = v
                    flat[f"{cat}_{k}"] = v

        # Если пришел формат API api-mobilespecs
        if "specifications" in raw and isinstance(raw["specifications"], list):
            for sec in raw["specifications"]:
                sec_title = sec.get("title", "").lower()
                for spec in sec.get("specs", []):
                    k = spec.get("key", "").lower().replace(" ", "_")
                    val_list = spec.get("val", [])
                    v = ", ".join(val_list) if isinstance(val_list, list) else str(val_list)
                    flat[k] = v
                    flat[f"{sec_title}_{k}"] = v

        return flat

    @staticmethod
    def _extract_brand(name: str) -> str:
        parts = name.split()
        return parts[0] if parts else "Unknown"

    @staticmethod
    def _clean_chipset_name(raw_soc: str) -> str:
        # Убирает технические индексы SM8650, нанометры и лишний мусор
        clean = re.sub(r"\bSM\d+-[A-Z0-9]+\b", "", raw_soc)
        clean = re.sub(r"\(\d+\s*nm\)", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean or raw_soc

    @staticmethod
    def _parse_launch_date(raw_date: Optional[str]) -> Optional[date]:
        if not raw_date:
            return None
        # Поиск года (например 2024)
        year_match = re.search(r"\b(201\d|202\d)\b", raw_date)
        if not year_match:
            return None
        year = int(year_match.group(1))

        # Поиск месяца
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month = 1
        for m_name, m_num in months.items():
            if m_name in raw_date.lower():
                month = m_num
                break

        return date(year, month, 1)

    @staticmethod
    def _extract_wattage(charging_str: str) -> Optional[int]:
        match = re.search(r"(\d+)\s*W", charging_str, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_memory_variants(mem_str: str) -> List[MemoryVariant]:
        """Парсит варианты памяти вида '128GB 8GB RAM, 256GB 12GB RAM'."""
        variants: List[MemoryVariant] = []
        if not mem_str:
            return variants

        # Шаблон: 256GB 8GB RAM или 1TB 12GB RAM
        pattern = r"(\d+)\s*(GB|TB)\s+(\d+)\s*GB\s+RAM"
        matches = re.findall(pattern, mem_str, re.IGNORECASE)
        for storage_num, unit, ram_num in matches:
            storage = int(storage_num)
            if unit.upper() == "TB":
                storage *= 1024
            ram = int(ram_num)

            # Базовая оценка стартовой цены в РФ в зависимости от памяти
            est_rub = 40000.0 + (storage / 256.0) * 25000.0
            variants.append(
                MemoryVariant(
                    ram_gb=ram,
                    storage_gb=storage,
                    msrp_local=round(est_rub / 1000) * 1000,
                    currency=Currency.RUB,
                )
            )

        return variants

    @staticmethod
    def _estimate_tier(name: str) -> str:
        name_lower = name.lower()
        if any(w in name_lower for w in ["ultra", "pro max", "fold", "magic v"]):
            return "Ultra-Flagship"
        if any(w in name_lower for w in ["pro", "plus", "+"]):
            return "Flagship"
        if any(w in name_lower for w in ["lite", "note", "a5", "gt"]):
            return "Sub-flagship"
        return "Mid-range"

    @staticmethod
    def _extract_series(name: str) -> str:
        parts = name.split()
        return " ".join(parts[1:3]) if len(parts) >= 3 else name

    @staticmethod
    def _estimate_forecast_profile(brand: str, name: str) -> ForecastProfile:
        brand_lower = brand.lower()
        if "apple" in brand_lower:
            return ForecastProfile(brand_decay_monthly_rate=0.022, expected_sweet_spot_months=12, historical_plateau_rv=0.72)
        if "samsung" in brand_lower:
            return ForecastProfile(brand_decay_monthly_rate=0.038, expected_sweet_spot_months=8, historical_plateau_rv=0.62)
        if "google" in brand_lower:
            return ForecastProfile(brand_decay_monthly_rate=0.045, expected_sweet_spot_months=6, historical_plateau_rv=0.55)
        return ForecastProfile(brand_decay_monthly_rate=0.050, expected_sweet_spot_months=6, historical_plateau_rv=0.54)
