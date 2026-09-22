"""Abstract Base Class for Smartphone Specifications and Analogs Providers."""

from abc import ABC, abstractmethod
from typing import List, Optional
from deprecio.models.device import Device


class BaseSpecsProvider(ABC):
    """Базовый интерфейс поставщика спецификаций и аналогов смартфонов."""

    @abstractmethod
    def get_device(self, model_id: str) -> Optional[Device]:
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
