"""Tests for safe BUSY client construction."""

from unittest.mock import MagicMock

import pytest

from custom_components.busybar import client as client_module


class FakeHass:
    """Small executor-only Home Assistant stand-in."""

    def __init__(self) -> None:
        self.executor_calls = 0

    async def async_add_executor_job(self, target):
        self.executor_calls += 1
        return target()


@pytest.mark.asyncio
async def test_client_is_constructed_in_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = object()
    constructor = MagicMock(return_value=expected)
    monkeypatch.setattr(client_module, "AsyncBusyBar", constructor)
    hass = FakeHass()

    client = await client_module.async_create_client(hass, "192.0.2.10", "secret")

    assert client is expected
    assert hass.executor_calls == 1
    constructor.assert_called_once_with("192.0.2.10", token="secret")
