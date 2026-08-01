"""Tests for BUSY Bar config-entry migrations."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.busybar import async_migrate_entry
from custom_components.busybar.const import CONF_DISPLAY_PRIORITY, CONF_ENTITIES


@pytest.mark.asyncio
async def test_migrates_legacy_display_priority_to_hardware_safe_value() -> None:
    entry = SimpleNamespace(
        version=1,
        options={CONF_ENTITIES: ["light.studio_lamp"], CONF_DISPLAY_PRIORITY: 95},
    )
    update_entry = MagicMock()
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=update_entry))

    assert await async_migrate_entry(hass, entry) is True

    update_entry.assert_called_once_with(
        entry,
        version=2,
        options={CONF_ENTITIES: ["light.studio_lamp"], CONF_DISPLAY_PRIORITY: 100},
    )


@pytest.mark.asyncio
async def test_migration_preserves_an_explicit_nonlegacy_priority() -> None:
    entry = SimpleNamespace(version=1, options={CONF_DISPLAY_PRIORITY: 80})
    update_entry = MagicMock()
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=update_entry))

    await async_migrate_entry(hass, entry)

    update_entry.assert_called_once_with(
        entry,
        version=2,
        options={CONF_DISPLAY_PRIORITY: 80},
    )
