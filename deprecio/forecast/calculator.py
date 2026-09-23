"""Price Decay Forecasting Engine for Smartphones."""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional
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
    decay = profile.brand_decay_monthly_rate

    points: List[ForecastPoint] = []
    milestones = [1, 2, 3, 6, 9, 12]

    for m in milestones:
        if m > months_horizon:
            continue

        # Экспоненциальное приближение к уровню плато
        decay_factor = (1.0 - decay) ** m
        pred_price = plateau_price + (current_price_rub - plateau_price) * decay_factor
        pred_price = round(pred_price / 100) * 100  # Округление до сотен рублей
        pred_rv = round((pred_price / current_price_rub) * 100, 1)

        # Сезонные триггеры падения цен
        trigger = None
        target_month = (today.month + m - 1) % 12 + 1
        if target_month == 11:
            trigger = "🏷️ Распродажа 11.11 (День холостяка)"
        elif target_month == 12:
            trigger = "🎄 Новогодние скидки"
        elif m == profile.expected_sweet_spot_months:
            trigger = "🟢 Вход в ценовое плато (Sweet Spot)"

        # Расчет будущей даты
        future_year = today.year + (today.month + m - 1) // 12
        points.append(
            ForecastPoint(
                months_ahead=m,
                target_date=f"{target_month:02d}.{future_year}",
                predicted_price_rub=pred_price,
                predicted_rv_percent=pred_rv,
                trigger_event=trigger,
            )
        )

    # Формирование итогового вердикта
    if profile.brand_decay_monthly_rate <= 0.03:
        summary = (
            f"🛡️ Высокая ликвидность ({device.brand}): медленный темп уценки "
            f"≈ {profile.brand_decay_monthly_rate * 100:.1f}% в месяц. Отлично держит цену."
        )
    else:
        summary = (
            f"⚡ Быстрая амортизация ({device.brand}): средний темп падения "
            f"≈ {profile.brand_decay_monthly_rate * 100:.1f}% в месяц. Оптимально покупать через "
            f"{profile.expected_sweet_spot_months} мес. после релиза."
        )

    return DeviceForecastReport(
        device_id=device.model_id,
        device_name=device.name,
        current_estimated_rub=current_price_rub,
        monthly_decay_rate=profile.brand_decay_monthly_rate,
        sweet_spot_month=profile.expected_sweet_spot_months,
        points=points,
        summary_verdict=summary,
    )
