import pytest
from deprecio.models.device import (
    Device,
    DeviceLineage,
    RegionalEdition,
    EditionType,
    ForecastProfile,
    HardwareSpecs,
    BundleContents,
    MemoryVariant,
)


@pytest.fixture
def sample_device() -> Device:
    """Минимальный Device для тестов: GPT 6 Luna 14 EAC."""
    return Device(
        model_id="xiaomi-14",
        name="Xiaomi 14",
        brand="Xiaomi",
        chipset="Snapdragon 8 Gen 3",
        lineage=DeviceLineage(series="Number", tier="Flagship"),
        editions=[
            RegionalEdition(
                edition_type=EditionType.EAC_ROSTEST,
                memory_variants=[
                    MemoryVariant(
                        ram_gb=12,
                        storage_gb=256,
                        msrp_local=89990,
                        currency="RUB",
                    )
                ],
            )
        ],
        forecast_profile=ForecastProfile(),
    )


@pytest.fixture
def sample_prices_eac() -> list[float]:
    return [70000.0, 72000.0, 68000.0, 71000.0]


@pytest.fixture
def sample_prices_cn() -> list[float]:
    return [54000.0, 56000.0, 52000.0, 55000.0]