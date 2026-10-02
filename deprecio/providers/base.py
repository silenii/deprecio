"""Abstract Base Class for Smartphone Specifications and Analogs Providers."""

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional
from deprecio.core.analytics_defaults import device_msrp_rub
from deprecio.models.device import Device


class BaseSpecsProvider(ABC):
    """Базовый интерфейс поставщика спецификаций и аналогов смартфонов."""

    @abstractmethod
    def get_device(self, model_id: str) -> Device:
        """Получить полную карточку смартфона по его ID."""
        pass

    @abstractmethod
    def search_devices(self, query: str) -> List[Device]:
        """Поиск устройств по названию, бренду или линейке."""
        pass

    @abstractmethod
    def find_analogs(
        self,
        device: Device,
        price_target_rub: Optional[float] = None,
        tolerance_percent: float = 0.15,
    ) -> List[Device]:
        """
        Поиск прямых конкурентов и аналогов смартфона:
        - схожий класс устройства (Tier);
        - сопоставимый чипсет / производительность;
        - ценовой коридор на вторичном рынке.
        """
        pass

    @staticmethod
    def filter_analogs(
        device: Device,
        candidates: Iterable[Device],
        price_target_rub: Optional[float],
        tolerance_percent: float,
    ) -> List[Device]:
        """Apply the shared analog, tier, and optional price-selection rules."""
        if not 0 <= tolerance_percent <= 1:
            raise ValueError("tolerance_percent должен быть в диапазоне от 0 до 1")
        if price_target_rub is not None and price_target_rub < 0:
            raise ValueError("price_target_rub не может быть отрицательным")

        analogs = [
            candidate
            for candidate in candidates
            if candidate.model_id != device.model_id
            and candidate.lineage.tier == device.lineage.tier
        ]
        if price_target_rub is None:
            return analogs

        lower = price_target_rub * (1 - tolerance_percent)
        upper = price_target_rub * (1 + tolerance_percent)
        analogs = [
            candidate
            for candidate in analogs
            if lower <= device_msrp_rub(candidate) <= upper
        ]
        return sorted(analogs, key=lambda candidate: abs(device_msrp_rub(candidate) - price_target_rub))
