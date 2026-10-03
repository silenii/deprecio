import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey

from deprecio.bot.handlers.compare import receive_second
from deprecio.bot.handlers.device import handle_device_search


def _message(text: str | None) -> SimpleNamespace:
    return SimpleNamespace(text=text, answer=AsyncMock())


def _state() -> FSMContext:
    return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))


def test_device_search_empty_result_is_reported():
    message = _message("unknown phone")
    state = _state()
    catalog = Mock(search_devices=Mock(return_value=[]), get_or_fetch_device=AsyncMock(return_value=None))
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    message.answer.return_value = status

    asyncio.run(handle_device_search(message, state, catalog))

    status.edit_text.assert_awaited_once()
    assert "ничего не найдено" in status.edit_text.await_args.args[0]
    assert asyncio.run(state.get_state()) is None


def test_device_search_provider_error_does_not_escape():
    message = _message("pixel 8")
    state = _state()
    catalog = Mock(search_devices=Mock(side_effect=RuntimeError("provider down")))
    status = SimpleNamespace(edit_text=AsyncMock())
    message.answer.return_value = status

    asyncio.run(handle_device_search(message, state, catalog))

    status.edit_text.assert_awaited_once()
    assert "Не удалось получить данные" in status.edit_text.await_args.args[0]


def test_compare_missing_device_is_reported_and_fsm_is_cleared():
    message = _message("pixel 8")
    state = _state()
    asyncio.run(state.set_data({"first_query": "unknown phone"}))
    catalog = Mock(search_devices=Mock(return_value=[]), get_or_fetch_device=AsyncMock(return_value=None))

    asyncio.run(receive_second(message, state, catalog, Mock()))

    message.answer.assert_awaited_once()
    assert "Не удалось найти" in message.answer.await_args.args[0]
    assert asyncio.run(state.get_state()) is None


def test_oversized_query_is_rejected():
    message = _message("x" * 101)
    state = _state()

    asyncio.run(handle_device_search(message, state, Mock()))

    message.answer.assert_awaited_once()
    assert "100 символов" in message.answer.await_args.args[0]
