"""Тесты модуля Provisioner — отправка конфигурационных SMS по ГОСТ 33465-2015.

Покрывает:
- Формирование EGTS-пакета команды (сервис 4, подзапись 51)
- Кодирование параметров APN, SERVER_ADDRESS, UNIT_ID
- Отправку SMS через CMW-500
- Обработку подтверждений (CT_COMCONF)
- Управление повторными попытками
"""

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.event_bus import EventBus
from core.provisioner import (
    CT_COM,
    CT_COMCONF,
    EGTS_GPRS_APN,
    EGTS_SERVER_ADDRESS,
    EGTS_UNIT_ID,
    Provisioner,
    ProvisioningConfig,
)


# =============================================================================
# Вспомогательные функции
# =============================================================================


def _make_config(
    apn: str = "internet.beeline.ru",
    server_address: str = "192.168.2.2:3001",
    unit_id: int = 42,
) -> ProvisioningConfig:
    """Создать тестовую конфигурацию."""
    return ProvisioningConfig(
        apn=apn,
        server_address=server_address,
        unit_id=unit_id,
    )


# =============================================================================
# Тесты ProvisioningConfig
# =============================================================================


class TestProvisioningConfig:
    """Тесты конфигурации provisioning."""

    def test_default_values(self) -> None:
        """Конфигурация по умолчанию."""
        config = ProvisioningConfig()

        assert config.apn == "internet.beeline.ru"
        assert config.server_address == "192.168.2.2:3001"
        assert config.unit_id == 0
        assert config.sms_retry_count == 3
        assert config.sms_retry_interval == 60.0
        assert config.network_ready_timeout == 45.0

    def test_custom_values(self) -> None:
        """Пользовательские значения конфигурации."""
        config = ProvisioningConfig(
            apn="custom.apn",
            server_address="10.0.0.1:5000",
            unit_id=123,
            sms_retry_count=5,
            sms_retry_interval=30.0,
            network_ready_timeout=60.0,
        )

        assert config.apn == "custom.apn"
        assert config.server_address == "10.0.0.1:5000"
        assert config.unit_id == 123
        assert config.sms_retry_count == 5
        assert config.sms_retry_interval == 30.0
        assert config.network_ready_timeout == 60.0

    def test_frozen(self) -> None:
        """Конфигурация неизменяема (frozen)."""
        config = _make_config()

        with pytest.raises(AttributeError):
            config.apn = "modified.apn"  # type: ignore[misc]


# =============================================================================
# Тесты формирования команды
# =============================================================================


class TestBuildCommandData:
    """Тесты формирования тела команды (CD)."""

    def test_build_command_data_basic(self) -> None:
        """Формирование базовой команды с тремя параметрами."""
        provisioner = Provisioner(EventBus())
        config = _make_config()

        data = provisioner._build_command_data(config)

        # Проверяем структуру данных
        assert len(data) > 0

        # Параметр 1: APN
        offset = 0
        assert data[offset] == 0x00  # ADR = 0
        assert data[offset + 1] == 0x02  # ACT = 2
        ccd = struct.unpack("<H", data[offset + 2 : offset + 4])[0]
        assert ccd == EGTS_GPRS_APN
        apn_len = data[offset + 4]
        apn_str = data[offset + 5 : offset + 5 + apn_len].decode("ascii")
        assert apn_str == "internet.beeline.ru"

        # Параметр 2: SERVER_ADDRESS
        offset = offset + 5 + apn_len
        assert data[offset] == 0x00  # ADR = 0
        assert data[offset + 1] == 0x02  # ACT = 2
        ccd = struct.unpack("<H", data[offset + 2 : offset + 4])[0]
        assert ccd == EGTS_SERVER_ADDRESS
        addr_len = data[offset + 4]
        addr_str = data[offset + 5 : offset + 5 + addr_len].decode("ascii")
        assert addr_str == "192.168.2.2:3001"

        # Параметр 3: UNIT_ID
        offset = offset + 5 + addr_len
        assert data[offset] == 0x00  # ADR = 0
        assert data[offset + 1] == 0x02  # ACT = 2
        ccd = struct.unpack("<H", data[offset + 2 : offset + 4])[0]
        assert ccd == EGTS_UNIT_ID
        unit_id_len = data[offset + 4]
        assert unit_id_len == 2
        unit_id = struct.unpack("<H", data[offset + 5 : offset + 7])[0]
        assert unit_id == 42

    def test_build_command_data_custom_apn(self) -> None:
        """Команда с пользовательским APN."""
        provisioner = Provisioner(EventBus())
        config = _make_config(apn="my.custom.apn")

        data = provisioner._build_command_data(config)

        # Ищем APN в данных
        apn_bytes = b"my.custom.apn"
        assert apn_bytes in data

    def test_build_command_data_custom_server(self) -> None:
        """Команда с пользовательским адресом сервера."""
        provisioner = Provisioner(EventBus())
        config = _make_config(server_address="10.20.30.40:8080")

        data = provisioner._build_command_data(config)

        addr_bytes = b"10.20.30.40:8080"
        assert addr_bytes in data


class TestBuildCommandSubrecord:
    """Тесты формирования подзаписи EGTS_SR_COMMAND_DATA."""

    def test_build_subrecord_structure(self) -> None:
        """Структура подзаписи соответствует ГОСТ."""
        provisioner = Provisioner(EventBus())
        command_data = b"\x00\x02\x01\x01\x05test"

        subrecord = provisioner._build_command_subrecord(command_data)

        # Проверяем минимальную длину
        assert len(subrecord) >= 7  # CT + CCT + CID + SID + flags + CD

        # CT = 0x05 (CT_COM)
        assert subrecord[0] == CT_COM

        # CCT = 0
        assert subrecord[1] == 0x00

        # CID (2 байта, little-endian)
        cid = struct.unpack("<H", subrecord[2:4])[0]
        assert 1 <= cid <= 65535

        # SID = 0
        assert subrecord[4] == 0x00

        # Флаги = 0
        assert subrecord[5] == 0x00

        # Тело команды
        assert subrecord[6:] == command_data

    def test_build_subrecord_unique_cid(self) -> None:
        """Каждая подзапись имеет уникальный CID."""
        provisioner = Provisioner(EventBus())
        command_data = b"\x00\x02\x01\x01\x05test"

        cids = set()
        for _ in range(100):
            subrecord = provisioner._build_command_subrecord(command_data)
            cid = struct.unpack("<H", subrecord[2:4])[0]
            cids.add(cid)

        # Все CID должны быть уникальными (или хотя бы большинство)
        assert len(cids) > 50


class TestBuildProvisioningCommand:
    """Тесты формирования полного EGTS-пакета."""

    def test_build_full_packet(self) -> None:
        """Формирование полного пакета provisioning."""
        provisioner = Provisioner(EventBus())
        config = _make_config()

        packet = provisioner.build_provisioning_command(config)

        # Пакет должен быть непустым
        assert len(packet) > 0
        assert isinstance(packet, bytes)


# =============================================================================
# Тесты отправки SMS
# =============================================================================


@pytest.mark.asyncio
class TestSendProvisioningSms:
    """Тесты отправки SMS."""

    async def test_send_sms_success(self) -> None:
        """Успешная отправка SMS."""
        event_bus = EventBus()
        cmw_driver = AsyncMock()
        cmw_driver.send_sms = AsyncMock(return_value=True)

        provisioner = Provisioner(event_bus, cmw_driver)
        config = _make_config()

        result = await provisioner.send_provisioning_sms("123456789012345", config)

        assert result is True
        cmw_driver.send_sms.assert_called_once()

    async def test_send_sms_without_cmw(self) -> None:
        """Отправка SMS без CMW-драйвера (эмуляция)."""
        event_bus = EventBus()
        provisioner = Provisioner(event_bus, cmw_driver=None)
        config = _make_config()

        events_received = []

        async def handler(event: str, data: dict) -> None:
            events_received.append((event, data))

        event_bus.on("provisioning.sms_sent")(handler)

        result = await provisioner.send_provisioning_sms("123456789012345", config)

        assert result is True
        assert len(events_received) == 1
        assert events_received[0][0] == "provisioning.sms_sent"

    async def test_send_sms_failure(self) -> None:
        """Ошибка отправки SMS."""
        event_bus = EventBus()
        cmw_driver = AsyncMock()
        cmw_driver.send_sms = AsyncMock(side_effect=Exception("Connection failed"))

        provisioner = Provisioner(event_bus, cmw_driver)
        config = _make_config()

        result = await provisioner.send_provisioning_sms("123456789012345", config)

        assert result is False


# =============================================================================
# Тесты обработки подтверждений
# =============================================================================


@pytest.mark.asyncio
class TestHandleConfirmation:
    """Тесты обработки подтверждений команд."""

    async def test_confirmation_success(self) -> None:
        """Успешное подтверждение команды."""
        event_bus = EventBus()
        provisioner = Provisioner(event_bus)

        packet = {
            "service": 4,
            "subrecord_type": 51,
            "command_type": CT_COMCONF,
            "command_id": 123,
            "command_status": 0,
        }

        result = await provisioner.handle_confirmation(packet)

        assert result is True

    async def test_confirmation_failure(self) -> None:
        """Подтверждение с ошибкой."""
        event_bus = EventBus()
        provisioner = Provisioner(event_bus)

        packet = {
            "service": 4,
            "subrecord_type": 51,
            "command_type": CT_COMCONF,
            "command_id": 123,
            "command_status": 5,  # Ошибка
        }

        result = await provisioner.handle_confirmation(packet)

        assert result is False

    async def test_not_a_confirmation(self) -> None:
        """Пакет не является подтверждением."""
        event_bus = EventBus()
        provisioner = Provisioner(event_bus)

        # Не тот сервис
        packet = {"service": 1}
        result = await provisioner.handle_confirmation(packet)
        assert result is None

        # Не та подзапись
        packet = {"service": 4, "subrecord_type": 10}
        result = await provisioner.handle_confirmation(packet)
        assert result is None

        # Не тот тип команды
        packet = {
            "service": 4,
            "subrecord_type": 51,
            "command_type": CT_COM,  # Запрос, не подтверждение
        }
        result = await provisioner.handle_confirmation(packet)
        assert result is None


# =============================================================================
# Тесты управления ожидающими подтверждениями
# =============================================================================


class TestPendingConfirmations:
    """Тесты управления ожидающими подтверждениями."""

    def test_register_pending(self) -> None:
        """Регистрация ожидающего подтверждения."""
        provisioner = Provisioner(EventBus())

        provisioner.register_pending(cid=123, imei="123456789012345", retries_left=3)

        pending = provisioner.get_pending(123)
        assert pending is not None
        assert pending["imei"] == "123456789012345"
        assert pending["retries_left"] == 3
        assert "created_at" in pending

    def test_unregister_pending(self) -> None:
        """Удаление ожидающего подтверждения."""
        provisioner = Provisioner(EventBus())

        provisioner.register_pending(cid=123, imei="123456789012345", retries_left=3)
        removed = provisioner.unregister_pending(123)

        assert removed is not None
        assert removed["imei"] == "123456789012345"

        # После удаления не должно быть
        assert provisioner.get_pending(123) is None

    def test_list_pending(self) -> None:
        """Получение списка ожидающих CID."""
        provisioner = Provisioner(EventBus())

        provisioner.register_pending(cid=1, imei="imei1", retries_left=3)
        provisioner.register_pending(cid=2, imei="imei2", retries_left=2)
        provisioner.register_pending(cid=3, imei="imei3", retries_left=1)

        cids = provisioner.list_pending()

        assert len(cids) == 3
        assert set(cids) == {1, 2, 3}

    def test_unregister_nonexistent(self) -> None:
        """Удаление несуществующего CID."""
        provisioner = Provisioner(EventBus())

        removed = provisioner.unregister_pending(999)

        assert removed is None
