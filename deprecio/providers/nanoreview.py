"""Adapter schema and parser interface for Nanoreview and Kimovil smartphone specs."""

from typing import Any, Dict, Optional
from deprecio.models.device import (
    Currency,
    Device,
    DeviceLineage,
    EditionType,
    HardwareSpecs,
    MemoryVariant,
    RegionalEdition,
)


class ExternalSpecsAdapter:
    """Адаптер для конвертации структур данных из внешних баз (Nanoreview / Kimovil) в модель Deprecio."""

    @staticmethod
    def parse_nanoreview_payload(raw_data: Dict[str, Any]) -> Optional[Device]:
        """
        Конвертирует сырой JSON-ответ или карточку агрегатора в Device.
        """
        try:
            model_name = raw_data.get("name", "Неизвестная модель")
            brand = raw_data.get("brand", "Unknown")
            chipset = raw_data.get("processor") or raw_data.get("soc")
            series = raw_data.get("series", "Standard")
            tier = raw_data.get("tier", "Mid-range")
            slug = raw_data.get("slug") or f"{brand.lower()}-{model_name.lower().replace(' ', '-')}"

            # Базовая конфигурация для рынка РФ/ЕАС
            variants = []
            for v in raw_data.get("variants", []):
                variants.append(
                    MemoryVariant(
                        ram_gb=v.get("ram", 8),
                        storage_gb=v.get("storage", 256),
                        msrp_local=float(v.get("price", 0.0)),
                        currency=Currency(v.get("currency", "RUB")),
                    )
                )

            edition = RegionalEdition(
                edition_type=EditionType.EAC_ROSTEST,
                announced=True,
                hardware=HardwareSpecs(
                    has_band_20=raw_data.get("has_band_20", True),
                    has_esim=raw_data.get("has_esim", False),
                    has_nfc=raw_data.get("has_nfc", True),
                ),
                memory_variants=variants,
            )

            return Device(
                model_id=slug,
                name=model_name,
                brand=brand,
                chipset=chipset,
                lineage=DeviceLineage(series=series, tier=tier),
                editions=[edition],
            )
        except Exception:
            return None
