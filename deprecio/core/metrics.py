"""Core Financial and Analytical Metrics for Smartphone Depreciation."""

from dataclasses import dataclass
from enum import Enum
import statistics
from typing import List, Optional


class MarketStage(str, Enum):
    RAPID_DECAY = "RAPID_DECAY"                 # 1-3 мес: фаза резкого первичного обвала цен
    APPROACHING_PLATEAU = "APPROACHING_PLATEAU" # 3-6 мес: замедление темпа уценки
    SWEET_SPOT = "SWEET_SPOT"                   # 6-18 мес: идеальный баланс актуальности и цены
    LEGACY_PLATEAU = "LEGACY_PLATEAU"           # > 18 мес: глубокая уценка, смена 2+ поколений


@dataclass
class SweetSpotAnalysis:
    """Результат анализа рациональности покупки на вторичном рынке."""
    is_sweet_spot: bool
    market_stage: MarketStage
    current_rv_percent: float
    total_drop_percent: float
    advice_buyer: str
    advice_seller: str


def calculate_residual_value(current_price: float, msrp_price: float) -> float:
    """
    Расчет остаточной стоимости (Residual Value %):
    RV = (P_current / P_msrp) * 100
    """
    if msrp_price <= 0:
        raise ValueError("Стартовая розничная цена (MSRP) должна быть строго положительной.")
    return round((current_price / msrp_price) * 100.0, 2)


def calculate_depreciation_drop(current_price: float, msrp_price: float) -> float:
    """
    Расчет общего процента падения цены от MSRP:
    Drop = - (100 - RV)
    """
    rv = calculate_residual_value(current_price, msrp_price)
    return round(rv - 100.0, 2)


def calculate_edition_gap(
    base_prices: List[float],
    comparison_prices: List[float],
) -> Optional[float]:
    """
    Расчет ценового разрыва между двумя региональными версиями (например, CN vs EAC):
    Gap = ((Median_comparison - Median_base) / Median_base) * 100%
    
    Отрицательное значение означает, что comparison-версия дешевле base-версии.
    """
    if not base_prices or not comparison_prices:
        return None

    median_base = statistics.median(base_prices)
    median_comp = statistics.median(comparison_prices)

    if median_base <= 0:
        return None

    gap = ((median_comp - median_base) / median_base) * 100.0
    return round(gap, 2)


def analyze_sweet_spot(
    months_since_release: int,
    current_price: float,
    msrp_price: float,
    expected_plateau_months: int = 6,
    historical_plateau_rv: float = 60.0,
) -> SweetSpotAnalysis:
    """
    Детекция фазы амортизации и зоны рациональной покупки (Sweet Spot).
    """
    rv = calculate_residual_value(current_price, msrp_price)
    drop = calculate_depreciation_drop(current_price, msrp_price)

    if months_since_release < 3:
        stage = MarketStage.RAPID_DECAY
        is_sweet = False
        advice_buyer = "Не рекомендуется к покупке на вторичке: цена еще активно падает на 4-6% в месяц."
        advice_seller = "Окно максимальной цены закрывается: если планируете продавать, продавайте немедленно."

    elif 3 <= months_since_release < expected_plateau_months:
        stage = MarketStage.APPROACHING_PLATEAU
        is_sweet = False
        advice_buyer = "Фаза стабилизации: можно присмотреться к предложениям с полным комплектом и торгом."
        advice_seller = "Цена стабилизируется. Резкого обвала в ближайший месяц не ожидается."

    elif expected_plateau_months <= months_since_release <= 18:
        stage = MarketStage.SWEET_SPOT
        is_sweet = True
        advice_buyer = "🟢 ЗОНА SWEET SPOT! Первоначальный обвал завершен, аппарат потерял максимум цены, сохраняя высокую актуальность."
        advice_seller = "Рыночная цена стабильна. Устройство ликвидно в своем классе."

    else:
        stage = MarketStage.LEGACY_PLATEAU
        is_sweet = False
        advice_buyer = "Глубокая уценка: отличный выбор для сверхбюджетной покупки, но проверяйте состояние АКБ и выгорание экрана."
        advice_seller = "Устройство перешло в категорию прошлых поколений. Спрос на вторичке умеренный."

    return SweetSpotAnalysis(
        is_sweet_spot=is_sweet,
        market_stage=stage,
        current_rv_percent=rv,
        total_drop_percent=drop,
        advice_buyer=advice_buyer,
        advice_seller=advice_seller,
    )
