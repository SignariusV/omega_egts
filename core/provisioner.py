"""Provisioner — модуль отправки конфигурационных SMS по ГОСТ 33465-2015.

Модуль реализует пассивный режим конфигурирования УСВ (Способ 1):
- Формирование EGTS-пакета команды с параметрами APN, IP сервера, UNIT_ID
- Отправка SMS через CMW-500
- Управление повторными попытками при отсутствии подтверждения

Ссылки на ГОСТ 33465-2015:
- Раздел 6.7.3: Сервис EGTS_COMMANDS_SERVICE, подзапись EGTS_SR_COMMAND_DATA
- Таблица 34: Параметры EGTS_GPRS_APN, EGTS_SERVER_ADDRESS, EGTS_UNIT_ID
- Раздел 5.7: Использование SMS (PDU-режим, 8-битная кодировка)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

from core.event_bus import EventBus
from libs.egts.registry import get_protocol
from libs.egts.models import Packet, Record


# =============================================================================
# Константы параметров конфигурации (таблица 34 ГОСТ)
# =============================================================================

EGTS_GPRS_APN = 0x0101  # Параметр: APN точки доступа GPRS
EGTS_SERVER_ADDRESS = 0x0102  # Параметр: Адрес сервера (IP:порт)
EGTS_UNIT_ID = 0x0103  # Параметр: Идентификатор устройства (UNIT_ID/TID)


# =============================================================================
# Типы команд (таблица 29 ГОСТ)
# =============================================================================

CT_COM = 0x05  # Команда установки параметров
CT_COMCONF = 0x85  # Подтверждение команды


# =============================================================================
# ProvisioningConfig
# =============================================================================

@dataclass(frozen=True)
class ProvisioningConfig:
    """Конфигурация для provisioning SMS.

    Attributes:
        apn: APN точки доступа (например, "internet.beeline.ru")
        server_address: Адрес сервера в формате "IP:порт"
        unit_id: Идентификатор устройства (TID)
        sms_retry_count: Количество повторных отправок SMS
        sms_retry_interval: Интервал между попытками (секунды)
        network_ready_timeout: Таймаут ожидания TCP из NETWORK_READY (секунды)
    """

    apn: str = "internet.beeline.ru"
    server_address: str = "192.168.2.2:3001"
    unit_id: int = 0
    sms_retry_count: int = 3
    sms_retry_interval: float = 60.0
    network_ready_timeout: float = 45.0


# =============================================================================
# Provisioner
# =============================================================================

class Provisioner:
    """Отправка конфигурационных SMS УСВ.

   Responsibilities:
    - Формирование EGTS-пакета команды (сервис 4, подзапись 51)
    - Кодирование параметров в бинарный формат
    - Отправка SMS через CMW-500
    - Отслеживание подтверждений (CT_COMCONF)
    - Управление повторными попытками

    Usage:
        provisioner = Provisioner(event_bus, cmw_driver)
        await provisioner.send_provisioning_sms(imei, config)
    """

    def __init__(self, event_bus: EventBus, cmw_driver: Any | None = None) -> None:
        """Инициализация Provisioner.

        Args:
            event_bus: Шина событий для публикации/подписки
            cmw_driver: Драйвер CMW-500 для отправки SMS (опционально)
        """
        self._event_bus = event_bus
        self._cmw_driver = cmw_driver
        self._pending_confirmations: dict[int, dict[str, Any]] = {}

    async def send_provisioning_sms(
        self,
        imei: str,
        config: ProvisioningConfig,
    ) -> bool:
        """Отправить SMS с конфигурацией.

        Args:
            imei: IMEI устройства для адресации SMS
            config: Параметры конфигурации

        Returns:
            True если SMS успешно отправлена
        """
        # Формируем EGTS-пакет команды
        packet_bytes = self.build_provisioning_command(config)

        # Отправляем SMS через CMW-500
        if self._cmw_driver is None:
            # Эмуляция для тестов
            await self._event_bus.emit(
                "provisioning.sms_sent",
                {
                    "imei": imei,
                    "config": {
                        "apn": config.apn,
                        "server_address": config.server_address,
                        "unit_id": config.unit_id,
                    },
                },
            )
            return True

        try:
            # CMW-500 отправляет SMS
            await self._cmw_driver.send_sms(imei, packet_bytes)

            # Публикуем событие об отправке
            await self._event_bus.emit(
                "provisioning.sms_sent",
                {
                    "imei": imei,
                    "packet_size": len(packet_bytes),
                    "config": {
                        "apn": config.apn,
                        "server_address": config.server_address,
                        "unit_id": config.unit_id,
                    },
                },
            )
            return True

        except Exception as e:
            await self._event_bus.emit(
                "provisioning.sms_failed",
                {"imei": imei, "error": str(e)},
            )
            return False

    def build_provisioning_command(self, config: ProvisioningConfig) -> bytes:
        """Построить EGTS-пакет команды конфигурации.

        Формат пакета:
        - Транспортный уровень: PT=1 (APPDATA), PID любой
        - Запись: SST=4 (COMMANDS_SERVICE), RST=4
        - Подзапись: SRT=51 (EGTS_SR_COMMAND_DATA)
        - Тело команды: CT=0x05 (CT_COM), параметры в формате TLV

        Args:
            config: Параметры конфигурации

        Returns:
            Бинарные данные SMS (PDU-формат)
        """
        # Импортируем для регистрации версии 2015
        import libs.egts._gost2015  # noqa: F401

        from libs.egts.registry import get_protocol
        protocol = get_protocol("2015")

        # Формируем тело команды (CD)
        command_data = self._build_command_data(config)

        # Формируем подзапись EGTS_SR_COMMAND_DATA (SRT=51)
        subrecord_data = self._build_command_subrecord(command_data)

        # Создаём объект Subrecord вручную
        from libs.egts.models import Subrecord
        subrecord = Subrecord(
            subrecord_type=51,  # EGTS_SR_COMMAND_DATA
            raw_bytes=subrecord_data,
        )

        # Формируем запись COMMANDS_SERVICE (SST=4)
        record = Record(
            rst=0,  # Запрос
            rn=1,  # Record Number
            rt=0,  # Request Type
            sst=4,  # EGTS_COMMANDS_SERVICE
            subrecords=[subrecord],
        )

        # Формируем транспортный пакет
        packet = Packet(
            pt=1,  # APPDATA
            pid=1,  # Любой PID
            fl=0,
            tm=0,
            sn=0,
            sdl=len(subrecord_data) + 10,  # Примерная длина
            records=[record],
        )

        return protocol.build_packet(packet)

    def _build_command_data(self, config: ProvisioningConfig) -> bytes:
        """Построить тело команды (CD) с параметрами.

        Формат параметра (таблица 30 ГОСТ):
        - ADR (1 байт): Адрес пространства параметров (0=основное)
        - ACT (1 байт): Действие (2=установка значения)
        - CCD (2 байта): Код параметра (0x0101, 0x0102, ...)
        - DT (переменная): Значение параметра

        Args:
            config: Параметры конфигурации

        Returns:
            Бинарные данные команды
        """
        data = bytearray()

        # Параметр 1: EGTS_GPRS_APN (строка)
        apn_bytes = config.apn.encode("ascii")
        data.append(0x00)  # ADR = 0
        data.append(0x02)  # ACT = 2 (установка значения)
        data.extend(struct.pack("<H", EGTS_GPRS_APN))  # CCD = 0x0101
        data.append(len(apn_bytes))  # Длина строки
        data.extend(apn_bytes)

        # Параметр 2: EGTS_SERVER_ADDRESS (строка "IP:порт")
        addr_bytes = config.server_address.encode("ascii")
        data.append(0x00)  # ADR = 0
        data.append(0x02)  # ACT = 2
        data.extend(struct.pack("<H", EGTS_SERVER_ADDRESS))  # CCD = 0x0102
        data.append(len(addr_bytes))
        data.extend(addr_bytes)

        # Параметр 3: EGTS_UNIT_ID (uint16)
        data.append(0x00)  # ADR = 0
        data.append(0x02)  # ACT = 2
        data.extend(struct.pack("<H", EGTS_UNIT_ID))  # CCD = 0x0103
        data.append(2)  # Длина uint16
        data.extend(struct.pack("<H", config.unit_id))

        return bytes(data)

    def _build_command_subrecord(self, command_data: bytes) -> bytes:
        """Построить подзапись EGTS_SR_COMMAND_DATA (SRT=51).

        Формат подзаписи (таблица 29 ГОСТ):
        - CT (1 байт): Тип команды (0x05=CT_COM)
        - CCT (1 байт): Счётчик команд (не используется, 0)
        - CID (2 байта): Идентификатор команды (уникальный)
        - SID (1 байт): Идентификатор сессии (0)
        - ACFE (1 бит): Флаг проверки подлинности (0)
        - CHSFE (1 бит): Флаг контрольной суммы (0)
        - CD (переменная): Тело команды

        Args:
            command_data: Тело команды (CD)

        Returns:
            Бинарные данные подзаписи
        """
        import random

        cid = random.randint(1, 65535)  # Уникальный CID

        subrecord = bytearray()
        subrecord.append(CT_COM)  # CT = 0x05
        subrecord.append(0x00)  # CCT = 0
        subrecord.extend(struct.pack("<H", cid))  # CID
        subrecord.append(0x00)  # SID = 0

        # Флаги: ACFE=0, CHSFE=0 (старшие биты первого байта после SID)
        # В ГОСТ флаги упакованы в первый байт, но для простоты используем 0
        subrecord.append(0x00)

        subrecord.extend(command_data)

        return bytes(subrecord)

    async def handle_confirmation(
        self,
        packet: dict[str, Any],
    ) -> bool | None:
        """Обработать подтверждение команды (CT_COMCONF).

        Args:
            packet: Распарсенный пакет от УСВ

        Returns:
            True если подтверждение успешное, False если ошибка,
            None если пакет не является подтверждением
        """
        # Проверяем, что это сервис команд
        if packet.get("service") != 4:
            return None

        # Проверяем подзапись
        subrecord_type = packet.get("subrecord_type")
        if subrecord_type != 51 and subrecord_type != "EGTS_SR_COMMAND_DATA":
            return None

        # Извлекаем CT (тип команды)
        ct = packet.get("command_type")
        if ct != CT_COMCONF:
            return None

        # Это подтверждение команды
        cid = packet.get("command_id")
        success = packet.get("command_status", 0) == 0

        # Публикуем событие подтверждения
        await self._event_bus.emit(
            "provisioning.confirmed",
            {
                "cid": cid,
                "success": success,
            },
        )

        return success

    def register_pending(
        self,
        cid: int,
        imei: str,
        retries_left: int,
    ) -> None:
        """Зарегистрировать ожидающее подтверждение.

        Args:
            cid: Идентификатор команды
            imei: IMEI устройства
            retries_left: Оставшееся количество попыток
        """
        self._pending_confirmations[cid] = {
            "imei": imei,
            "retries_left": retries_left,
            "created_at": __import__("time").time(),
        }

    def unregister_pending(self, cid: int) -> dict[str, Any] | None:
        """Удалить ожидающее подтверждение.

        Args:
            cid: Идентификатор команды

        Returns:
            Данные подтверждения или None
        """
        return self._pending_confirmations.pop(cid, None)

    def get_pending(self, cid: int) -> dict[str, Any] | None:
        """Получить данные ожидающего подтверждения.

        Args:
            cid: Идентификатор команды

        Returns:
            Данные подтверждения или None
        """
        return self._pending_confirmations.get(cid)

    def list_pending(self) -> list[int]:
        """Получить список ожидающих CID.

        Returns:
            Список CID
        """
        return list(self._pending_confirmations.keys())
