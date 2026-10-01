"""FSM handler for side-by-side smartphone comparison."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from deprecio.core import analyze_sweet_spot, calculate_residual_value
from deprecio.providers import CachedSpecsProvider
from deprecio.harvester import MarketAggregator
from deprecio.core.analytics_defaults import device_msrp_rub

router = Router(name="compare_router")


class CompareStates(StatesGroup):
    waiting_first = State()
    waiting_second = State()


def _msrp_rub(device) -> float:
    """Return normalized MSRP using the shared analytical defaults."""
    return device_msrp_rub(device)


async def _find_device(query: str, catalog: CachedSpecsProvider):
    matches = catalog.search_devices(query)
    return matches[0] if matches else await catalog.get_or_fetch_device(query)


def _table(rows: list[tuple[str, str, str]]) -> str:
    headers = ("Параметр", rows[0][1], rows[0][2])
    widths = [max(len(row[index]) for row in rows + [headers]) for index in range(3)]
    separator = "|" + "|".join("-" * (width + 2) for width in widths) + "|"
    lines = [
        "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(headers)) + " |",
        separator,
    ]
    lines.extend(
        "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |"
        for row in rows
    )
    return "\n".join(lines)


async def _comparison(first, second, catalog: CachedSpecsProvider, market_aggregator: MarketAggregator) -> str:
    first_stats, second_stats = await catalog.get_market_stats(first), await catalog.get_market_stats(second)
    first_price, second_price = first_stats.median_price_rub, second_stats.median_price_rub
    first_rv = calculate_residual_value(first_price, _msrp_rub(first))
    second_rv = calculate_residual_value(second_price, _msrp_rub(second))

    def sweet_spot(device, price: float, msrp: float) -> str:
        analysis = analyze_sweet_spot(8, price, msrp)
        return "✅ Сейчас" if analysis.is_sweet_spot else "⏳ Через 3 мес."

    def cn_gap(stats) -> float:
        cn = stats.editions.get("CN")
        eac = stats.editions.get("EAC") or stats.editions.get("EAC_ROSTEST")
        if not cn or not eac or not eac.median_price_rub:
            return 0.0
        return (cn.median_price_rub - eac.median_price_rub) / eac.median_price_rub * 100

    rows = [
        ("Чипсет", first.chipset or "Нет данных", second.chipset or "Нет данных"),
        ("Класс", first.lineage.tier, second.lineage.tier),
        ("Медиана Авито", f"≈ {first_price:,.0f} ₽", f"≈ {second_price:,.0f} ₽"),
        ("RV%", f"{first_rv:.1f}%", f"{second_rv:.1f}%"),
        ("Sweet Spot", sweet_spot(first, first_price, _msrp_rub(first)), sweet_spot(second, second_price, _msrp_rub(second))),
        ("CN дешевле EAC", f"{cn_gap(first_stats):+.0f}%", f"{cn_gap(second_stats):+.0f}%"),
    ]
    rv_gap = second_rv - first_rv
    better = second.name if rv_gap >= 0 else first.name
    advantage = abs(rv_gap)
    verdict = f"💡 Вывод: {better} держит цену лучше (+{advantage:.1f} RV%)."
    if first_price <= second_price:
        verdict += f"\n   {first.name} — выгоднее сейчас, {second.name} — для перепродажи."
    else:
        verdict += f"\n   {second.name} — выгоднее сейчас, {first.name} — для перепродажи."
    return f"⚖️ Сравнение: {first.name} vs {second.name}\n\n```\n{_table(rows)}\n```\n\n{verdict}"


@router.message(Command("compare"))
async def start_compare(message: Message, state: FSMContext) -> None:
    await state.set_state(CompareStates.waiting_first)
    await message.answer("Введите первую модель:")


@router.message(CompareStates.waiting_first)
async def receive_first(message: Message, state: FSMContext) -> None:
    if not message.text or message.text.startswith("/"):
        await message.answer("Введите название первой модели текстом:")
        return
    await state.update_data(first_query=message.text.strip())
    await state.set_state(CompareStates.waiting_second)
    await message.answer("Теперь введите вторую модель:")


@router.message(CompareStates.waiting_second)
async def receive_second(message: Message, state: FSMContext, catalog: CachedSpecsProvider,
                         market_aggregator: MarketAggregator) -> None:
    if not message.text or message.text.startswith("/"):
        await message.answer("Введите название второй модели текстом:")
        return
    data = await state.get_data()
    await state.clear()
    first = await _find_device(data["first_query"], catalog)
    second = await _find_device(message.text.strip(), catalog)
    if not first or not second:
        await message.answer("Не удалось найти одну из моделей. Попробуйте ещё раз через /compare.")
        return
    await message.answer(await _comparison(first, second, catalog, market_aggregator), parse_mode="Markdown")
