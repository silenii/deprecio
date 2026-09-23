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
        rel_year = release_date.year if release_date else None
        tier = cls._estimate_tier(name)
        variants = cls._parse_memory_variants(memory_str, brand, tier, release_year=rel_year)
        if not variants:
            default_msrp = 19990.0 if (rel_year and rel_year <= 2019) else 49990.0
            variants = [MemoryVariant(ram_gb=4 if (rel_year and rel_year <= 2019) else 8, storage_gb=64 if (rel_year and rel_year <= 2019) else 128, msrp_local=default_msrp, currency=Currency.RUB)]

        # 8. Сборка версий (Global / EAC)
        # 8. Сборка версий (Ростест/EAC, Global, CN, US)
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

        editions = cls._generate_regional_editions(brand, name, release_date, hardware, bundle, variants)

        # 9. Профиль уценки бренда
        profile = cls._estimate_forecast_profile(brand, name)

        return Device(
            model_id=slug,
            name=name,
            brand=brand,
            chipset=clean_chipset,
            lineage=DeviceLineage(series=cls._extract_series(name), tier=cls._estimate_tier(name)),
            editions=editions,
            forecast_profile=profile,
        )

    @classmethod
    def _generate_regional_editions(
        cls,
        brand: str,
        name: str,
        release_date: Optional[date],
        hardware: HardwareSpecs,
        bundle: BundleContents,
        variants: List[MemoryVariant],
    ) -> List[RegionalEdition]:
        """Генерирует полный спектр региональных версий (Ростест, Global, CN, US) с точными отличиями."""
        editions: List[RegionalEdition] = []
        brand_lower = brand.lower()
        name_lower = name.lower()

        # 1. Официальная версия Ростест / EAC
        eac_variants = [
            MemoryVariant(ram_gb=v.ram_gb, storage_gb=v.storage_gb, msrp_local=v.msrp_local, currency=Currency.RUB)
            for v in variants
        ]
        editions.append(
            RegionalEdition(
                edition_type=EditionType.EAC_ROSTEST,
                announced=True,
                release_date=release_date,
                os_name=f"{brand} OS (EAC)",
                hardware=HardwareSpecs(
                    has_band_20=True,
                    has_band_7=True,
                    has_band_3=True,
                    has_esim=hardware.has_esim,
                    sim_slots=hardware.sim_slots,
                    has_nfc=hardware.has_nfc,
                    display_pwm_hz=hardware.display_pwm_hz,
                ),
                bundle=bundle,
                memory_variants=eac_variants,
            )
        )

        # 2. Глобальная версия (Global / EU)
        global_variants = [
            MemoryVariant(ram_gb=v.ram_gb, storage_gb=v.storage_gb, msrp_local=round(v.msrp_local * 0.93 / 1000) * 1000, currency=Currency.RUB)
            for v in variants
        ]
        editions.append(
            RegionalEdition(
                edition_type=EditionType.GLOBAL_EU,
                announced=True,
                release_date=release_date,
                os_name="Global Multilingual OS",
                hardware=HardwareSpecs(
                    has_band_20=True,
                    has_band_7=True,
                    has_band_3=True,
                    has_esim=hardware.has_esim,
                    sim_slots=hardware.sim_slots,
                    has_nfc=hardware.has_nfc,
                    display_pwm_hz=hardware.display_pwm_hz,
                ),
                bundle=bundle,
                memory_variants=global_variants,
            )
        )

        # 3. Китайская версия (CN) для азиатских брендов или Apple/Samsung
        # У китайских версий обычно нет Band 20 (кроме некоторых топ-флагманов), вилка китайская, цена ниже на 18-22%
        cn_variants = [
            MemoryVariant(ram_gb=v.ram_gb, storage_gb=v.storage_gb, msrp_local=round(v.msrp_local * 0.80 / 1000) * 1000, currency=Currency.RUB)
            for v in variants
        ]
        is_apple = "apple" in brand_lower or "iphone" in name_lower
        cn_sim = "2x NanoSIM (нет eSIM)" if is_apple else hardware.sim_slots
        cn_hardware = HardwareSpecs(
            has_band_20=False,  # В Китае нет Band 20
            has_band_7=True,
            has_band_3=True,
            has_esim=False if is_apple else hardware.has_esim,
            sim_slots=cn_sim,
            has_nfc=hardware.has_nfc,
            display_pwm_hz=hardware.display_pwm_hz,
        )
        editions.append(
            RegionalEdition(
                edition_type=EditionType.CN,
                announced=True,
                release_date=release_date,
                os_name="CN Firmware (Chinese / English)",
                hardware=cn_hardware,
                bundle=bundle,
                memory_variants=cn_variants,
            )
        )

        # 4. Версия для США (US) для Apple и Samsung
        if is_apple or "samsung" in brand_lower:
            us_variants = [
                MemoryVariant(ram_gb=v.ram_gb, storage_gb=v.storage_gb, msrp_local=round(v.msrp_local * 0.88 / 1000) * 1000, currency=Currency.RUB)
                for v in variants
            ]
            is_recent_iphone = is_apple and release_date and release_date.year >= 2022
            us_sim = "eSIM only (без физ. слота)" if is_recent_iphone else "1x NanoSIM + eSIM"
            editions.append(
                RegionalEdition(
                    edition_type=EditionType.US,
                    announced=True,
                    release_date=release_date,
                    os_name="US Carrier / Factory Unlocked",
                    hardware=HardwareSpecs(
                        has_band_20=True,
                        has_band_7=True,
                        has_band_3=True,
                        has_esim=True,
                        sim_slots=us_sim,
                        has_nfc=hardware.has_nfc,
                        display_pwm_hz=hardware.display_pwm_hz,
                    ),
                    bundle=bundle,
                    memory_variants=us_variants,
                )
            )

        return editions

    @classmethod
    def _flatten_specs(cls, raw: Dict[str, Any]) -> Dict[str, str]:
        """Приводит спецификации из разных форматов к единому плоскому словарю."""
        flat: Dict[str, str] = {}

        # 1. Прямые ключи в raw
        for k, v in raw.items():
            if isinstance(v, str):
                flat[k.lower().replace(" ", "_")] = v

        # 2. Вложенный dict specifications
        if "specifications" in raw and isinstance(raw["specifications"], dict):
            for k, v in raw["specifications"].items():
                if isinstance(v, str):
                    flat[k.lower().replace(" ", "_")] = v

        # 3. Если пришла таблица specs
        if "specifications_table" in raw:
            for cat, fields in raw["specifications_table"].items():
                for k, v in fields.items():
                    flat[k] = v
                    flat[f"{cat}_{k}"] = v

        # 4. Если пришел формат API api-mobilespecs
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
        # Поиск года (от 1999 до 2029)
        year_match = re.search(r"\b(199\d|200\d|201\d|202\d)\b", raw_date)
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
    def _parse_memory_variants(mem_str: str, brand: str, tier: str, release_year: Optional[int] = None) -> List[MemoryVariant]:
        """Парсит варианты памяти вида '128GB 8GB RAM, 256GB 12GB RAM'."""
        variants: List[MemoryVariant] = []
        if not mem_str:
            return variants

        # Шаблон: 256GB 8GB RAM или 1TB 12GB RAM
        pattern = r"(\d+)\s*(GB|TB)\s+(\d+)\s*GB\s+RAM"
        matches = re.findall(pattern, mem_str, re.IGNORECASE)
        
        b_lower = brand.lower()
        # Коэффициент бренда (Apple/Samsung стоят дороже китайских аналогов)
        brand_coef = 1.0
        if any(b in b_lower for b in ["apple", "samsung", "google", "sony", "asus"]):
            brand_coef = 1.15
        elif any(b in b_lower for b in ["xiaomi", "redmi", "poco", "realme", "infinix", "tecno", "itel"]):
            brand_coef = 0.75
        elif any(b in b_lower for b in ["vivo", "iqoo", "oppo", "oneplus", "honor"]):
            brand_coef = 0.85

        for storage_num, unit, ram_num in matches:
            storage = int(storage_num)
            if unit.upper() == "TB":
                storage *= 1024
            ram = int(ram_num)

            # Базовая цена в зависимости от класса (tier) и года
            base_rub = 20000.0
            if tier == "Budget":
                base_rub = 8000.0
            elif tier == "Mid-range":
                base_rub = 20000.0
            elif tier == "Sub-flagship":
                base_rub = 40000.0
            elif tier == "Flagship":
                base_rub = 70000.0
            elif tier == "Ultra-Flagship":
                base_rub = 100000.0

            # Поправка на инфляцию/год
            if release_year and release_year <= 2019:
                base_rub *= 0.5
            elif release_year and release_year <= 2021:
                base_rub *= 0.75

            # Добавка за память (грубая оценка: +5000 за каждые 128GB сверх базовых 64)
            storage_premium = max(0, ((storage - 64) / 128.0) * 5000.0)
            
            est_rub = (base_rub + storage_premium) * brand_coef

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
        
        if any(w in name_lower for w in ["ultra", "pro max", "pro+", "pro plus", "fold", "magic v"]):
            return "Ultra-Flagship"
            
        # Flagships (but rule out sub-flagships that just use 'Pro')
        if any(w in name_lower for w in ["pro", "plus", "+"]):
            # Exemptions: budget/midrange phones with 'Pro' (e.g. Poco X6 Pro, Redmi Note 13 Pro)
            if any(w in name_lower for w in ["poco", "redmi", "c", "m", "y"]):
                return "Sub-flagship"
            return "Flagship"
            
        if any(w in name_lower for w in ["gt", "x"]):
            if "poco x" in name_lower:
                return "Mid-range"
            return "Flagship"

        if any(w in name_lower for w in ["lite", "fe", "a5", "neo"]):
            return "Sub-flagship"
            
        if any(w in name_lower for w in ["a0", "a1", "a2", "a3", "c", "y", "spark", "smart", "pop"]):
            return "Budget"
            
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
