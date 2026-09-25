"""Price Decay Forecasting Engine for Smartphones."""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional
from dateutil.relativedelta import relativedelta
from deprecio.models.device import Device, ForecastProfile



@dataclass
class ForecastPoint:
    """Точка на прогнозируемой кривой падения цены."""
    months_ahead: int
    target_date: str
    predicted_price_rub: float
    predicted_rv_percent: float
    trigger_event: Optional[str] = None


@dataclass
class DeviceForecastReport:
    """Полный аналитический отчет прогнозирования уценки модели."""
    device_id: str
    device_name: str
    current_estimated_rub: float
    monthly_decay_rate: float
    sweet_spot_month: int
    points: List[ForecastPoint]
    summary_verdict: str


def generate_price_forecast(
    device: Device,
    current_price_rub: float,
    months_horizon: int = 12,
    base_date: Optional[date] = None,
) -> DeviceForecastReport:
    """
    Генерирует прогноз падения цены на основе профиля модели и динамики бренда.
    
    Использует адаптивную формулу затухающего экспоненциального падения:
    P(t) = P_plateau + (P_current - P_plateau) * (1 - decay_rate)^t
    """
    profile = device.forecast_profile or ForecastProfile()
    today = base_date or date.today()

    # Оценка плато (минимальной равновесной цены вторички для данного класса)
    plateau_price = current_price_rub * profile.historical_plateau_rv
    decay_rate = profile.brand_decay_monthly_rate

    points: List[ForecastPoint] = []

    # Расчет для каждого месяца от 1 до months_horizon
    for t in range(1, months_horizon + 1):
        # Экспоненциальное приближение к уровню плато
        decay_factor = (1.0 - decay_rate) ** t
        predicted = plateau_price + (current_price_rub - plateau_price) * decay_factor
        
        # Расчет целевой даты
        target_date = (today + relativedelta(months=t)).isoformat()
        
        # Определение trigger_event
        trigger_event = None
        if t == profile.expected_sweet_spot_months:
            trigger_event = "Sweet Spot"
        
        # Добавление точки прогноза
        points.append(
            ForecastPoint(
                months_ahead=t,
                target_date=target_date,
                predicted_price_rub=round(predicted, 0),
                predicted_rv_percent=round((predicted / current_price_rub) * 100, 1),
                trigger_event=trigger_event,
            )
        )

    # Формирование итогового вердикта
    if decay_rate < 0.03:
        summary_verdict = "Медленная амортизация: устройство хорошо держит цену"
    elif decay_rate < 0.06:
        summary_verdict = "Стандартная амортизация: типичная для флагманов"
    else:
        summary_verdict = "Быстрая амортизация: характерна для китайских суббрендов"

    return DeviceForecastReport(
        device_id=device.model_id,
        device_name=device.name,
        current_estimated_rub=current_price_rub,
        monthly_decay_rate=profile.brand_decay_monthly_rate,
        sweet_spot_month=profile.expected_sweet_spot_months,
        points=points,
        summary_verdict=summary_verdict,
    )
