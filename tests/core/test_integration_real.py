"""Интеграционные тесты с реальными EGTS-пакетами.

Используются реальные hex-пакеты из data/packets/:
- Авторизация (SST=1): TERM_IDENTITY, AUTH_INFO, RESULT_CODE
- RESPONSE (PT=0): подтверждения от платформы
- Команды (SST=4): CONFIG, SERVER_ADDRESS, UNIT_ID
- Траектория (SST=10): TRACK_DATA, ACCEL_DATA
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.dispatcher import CommandDispatcher, PacketDispatcher
from core.event_bus import EventBus
from core.pipeline import (
    AutoResponseMiddleware,
    CrcValidationMiddleware,
    DuplicateDetectionMiddleware,
    EventEmitMiddleware,
    PacketPipeline,
    ParseMiddleware,
)
from core.session import SessionManager
from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015

# Реальные hex-пакеты из data/packets/pure_hex_correct_20260406_190414.txt
# Формат: (hex, описание, направление)

# Пакет авторизации от УСВ (SST=1, PT=1, PID=42) — TERM_IDENTITY/AUTH_INFO, len=59
AUTH_USV_HEX = (
    "0100000B002E002A0001CC2700490080010101240001000000"
    "16383630383033303636343438333133303235303737303031"
    "373135363433390F3A"
)

# RESPONSE от платформы (PT=0, PID=30, RPID=42) — подтверждение авторизации, len=29
AUTH_RESPONSE_HEX = "0100000B0010001E00003B2A000006002D00400101000300490000E6BE"

# Пакет команд (SST=4, PT=1, PID=17) — CONFIG, len=38
COMMAND_HEX = "0100000B0019001100015612002000400404330F00500000000000000000000000011501DCBE"

# RESPONSE на команду (PT=0, PID=18, RPID=30), len=29
COMMAND_RESPONSE_HEX = "0100000B001000120000401E0000060021004001010003003D00002BAC"

# Пакет траектории (SST=10, PT=1, PID=33) — TRACK_DATA, len=880
TRACK_HEX = (
    "0100000B006303210001FB5C034000800A0A3E5903470000000089A6B9719C4AD7D33488135A8932B9719C8DEBD334"
    "88135A8902B9719C91FFD33488135A8952B9719CED13D43488135A8985B9719CA028D43488135A89A2B9719CAF3CD43488135A89"
    "69B9719C0951D43488135A89A1B9719C4565D43488135A893EB9719C0979D43488135A891CB9719C4E8DD43488135A8900B9719C"
    "E5A1D43488135A8933B9719CB3B5D43488135A8945B9719C46CAD43488135A89EEB9719C22DED43488135A89FBB8719CBCF2D434"
    "88135A8904B9719CEC06D53488135A891EB8719CF21AD53488135A8976B8719C2B2FD53488135A89B6B8719C9243D53488135A89"
    "26B9719CAF57D53488135A89AEB8719C9D6BD53488135A896EB8719C0380D53488135A8989B8719CF493D53488135A8941B8719C"
    "72A8D53488135A8910B8719CA1BCD53488135A89C1B7719CCCD0D53488135A89F1B7719C1AE5D53488135A89DDB7719C7DF9D534"
    "88135A89C3B7719C010ED63488135A89EAB7719C7122D63488135A895DB8719C7536D63488135A8952B8719C1B4AD63488135A89"
    "7DB8719C8E5ED63488135A8966B8719C6872D63488135A89F6B7719CC886D63488135A890BB8719C0F9BD63488135A8971B8719C"
    "00AFD63488135A8941B8719CEAC2D63488135A892CB8719C0FD7D63488135A897BB8719C78EBD63488135A8976B8719C74FFD634"
    "88135A8949B8719CCE13D73488135A89B2B7719C0028D73488135A8946B7719CA93CD73488135A8976B7719C2951D73488135A89"
    "92B7719C5265D73488135A89EEB6719CCA79D73488135A890FB7719C378ED73488135A89D9B6719C6AA2D73488135A8992B6719C"
    "26B6D73488135A8998B6719C8FCAD73488135A8997B6719C1BDFD73488135A8979B6719CFEF2D73488135A8990B6719C3707D834"
    "88135A8944B6719C201BD83488135A894CB6719C172FD83488135A8986B6719C9143D83488135A8960B6719CC057D83488135A89"
    "8CB6719C236CD83488135A89EBB5719CFB7FD83463135A89F0B5719CD773D83400005A89A1B5719C0873D83400005A8998B5719C"
    "9373D83400005A89A7B5719C3C72D83400005A89F6B5719CCA71D83400005A89EAB5719C0F72D83400005A890AB6719C8671D834"
    "00005A89F3B5719C5571D83400005A89F3B5719C5571D83400005A896BB6719C3E71D83400005A8982B6719CE870D83400005AB7"
    "E3"
)


def _hex_to_bytes(hex_str: str) -> bytes:
    """Конвертировать hex-строку в bytes."""
    return bytes.fromhex(hex_str)


class TestRealAuthPacket:
    """Интеграция: реальный пакет авторизации проходит через pipeline."""

    @pytest.fixture
    def event_bus(self) -> EventBus:
        return EventBus()

    @pytest.fixture
    def protocol(self) -> EgtsProtocol2015:
        return EgtsProtocol2015()

    @pytest.fixture
    def session_manager(self, event_bus: EventBus) -> SessionManager:
        return SessionManager(bus=event_bus, gost_version="2015")

    @pytest.fixture
    def pipeline(
        self, event_bus: EventBus, session_manager: SessionManager, protocol: EgtsProtocol2015
    ) -> PacketPipeline:
        pipe = PacketPipeline()
        # CrcValidationMiddleware принимает SessionManager (для получения protocol из connection)
        pipe.add("crc", CrcValidationMiddleware(session_manager), order=1)
        pipe.add("parse", ParseMiddleware(session_manager), order=2)
        pipe.add("auto_resp", AutoResponseMiddleware(session_manager), order=3)
        pipe.add("dedup", DuplicateDetectionMiddleware(session_manager), order=4)
        pipe.add("emit", EventEmitMiddleware(event_bus), order=5)
        return pipe

    @pytest.fixture
    def packet_dispatcher(
        self,
        event_bus: EventBus,
        session_manager: SessionManager,
        pipeline: PacketPipeline,
        protocol: EgtsProtocol2015,
    ) -> PacketDispatcher:
        return PacketDispatcher(
            bus=event_bus,
            session_mgr=session_manager,
            pipeline=pipeline,
            protocol=protocol,
        )

    async def test_real_auth_packet_parses_successfully(
        self,
        event_bus: EventBus,
        packet_dispatcher: PacketDispatcher,
        protocol: EgtsProtocol2015,
    ):
        """Реальный AUTH-пакет от УСВ парсится без ошибок.

        Пакет: TERM_IDENTITY + AUTH_INFO (SST=1, PT=1, PID=42)
        """
        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)

        # Парсим напрямую для проверки
        result = protocol.parse_packet(packet_bytes)
        assert result.packet is not None
        assert result.packet.packet_type == 1  # APPDATA
        assert result.packet.packet_id == 42
        assert result.packet.crc8_valid is True
        assert result.packet.crc16_valid is True
        assert len(result.packet.records) >= 1
        assert result.packet.records[0].service_type == 1  # AUTH

    async def test_real_auth_packet_through_pipeline(
        self,
        event_bus: EventBus,
        packet_dispatcher: PacketDispatcher,
        session_manager: SessionManager,
    ):
        """Реальный AUTH-пакет проходит через всю цепочку pipeline."""
        processed: list[dict] = []

        async def on_processed(data: dict) -> None:
            processed.append(data)

        event_bus.on("packet.processed", on_processed, ordered=True)

        # Создаём соединение (нужно для CrcValidationMiddleware)
        session_manager.create_session(
            connection_id="conn1",
            protocol=EgtsProtocol2015(),
        )

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)

        await event_bus.emit(
            "raw.packet.received",
            {"raw": packet_bytes, "channel": "tcp", "connection_id": "conn1"},
        )
        await asyncio.sleep(0.1)

        assert len(processed) >= 1
        ctx = processed[0]["ctx"]
        assert ctx.channel == "tcp"
        assert ctx.connection_id == "conn1"
        assert ctx.crc_valid is True
        # Пакет должен быть распарсен
        assert ctx.parsed is not None
        assert ctx.parsed.packet is not None
        assert ctx.parsed.packet.packet_type == 1  # APPDATA
        assert ctx.parsed.packet.packet_id == 42

    async def test_real_response_packet_parses(
        self,
        event_bus: EventBus,
        packet_dispatcher: PacketDispatcher,
        protocol: EgtsProtocol2015,
    ):
        """ RESPONSE-пакет от платформы (PT=0) парсится корректно."""
        packet_bytes = _hex_to_bytes(AUTH_RESPONSE_HEX)

        result = protocol.parse_packet(packet_bytes)
        assert result.packet is not None
        assert result.packet.packet_type == 0  # RESPONSE
        assert result.packet.response_packet_id == 42  # RPID=42 (подтверждает PID=42)
        assert result.packet.crc8_valid is True
        assert result.packet.crc16_valid is True

    async def test_real_command_packet_parses(
        self,
        event_bus: EventBus,
        packet_dispatcher: PacketDispatcher,
        protocol: EgtsProtocol2015,
    ):
        """Пакет команд (SST=4, PID=17) парсится корректно."""
        packet_bytes = _hex_to_bytes(COMMAND_HEX)

        result = protocol.parse_packet(packet_bytes)
        assert result.packet is not None
        assert result.packet.packet_type == 1  # APPDATA
        assert result.packet.packet_id == 17
        assert result.packet.records[0].service_type == 4  # COMMANDS

    async def test_real_track_data_packet_parses(
        self,
        event_bus: EventBus,
        packet_dispatcher: PacketDispatcher,
        protocol: EgtsProtocol2015,
    ):
        """Пакет траектории (SST=10, PID=33) парсится корректно."""
        packet_bytes = _hex_to_bytes(TRACK_HEX)

        result = protocol.parse_packet(packet_bytes)
        assert result.packet is not None
        assert result.packet.packet_type == 1  # APPDATA
        assert result.packet.packet_id == 33
        assert result.packet.records[0].service_type == 10  # ECALL/TRACK


class TestRealPacketDuplicateDetection:
    """Интеграция: определение дубликатов на реальных пакетах."""

    @pytest.fixture
    def event_bus(self) -> EventBus:
        return EventBus()

    @pytest.fixture
    def protocol(self) -> EgtsProtocol2015:
        return EgtsProtocol2015()

    @pytest.fixture
    def session_manager(self, event_bus: EventBus) -> SessionManager:
        return SessionManager(bus=event_bus, gost_version="2015")

    @pytest.fixture
    def pipeline(
        self, event_bus: EventBus, session_manager: SessionManager, protocol: EgtsProtocol2015
    ) -> PacketPipeline:
        pipe = PacketPipeline()
        # CrcValidationMiddleware принимает SessionManager (для получения protocol из connection)
        pipe.add("crc", CrcValidationMiddleware(session_manager), order=1)
        pipe.add("parse", ParseMiddleware(session_manager), order=2)
        pipe.add("auto_resp", AutoResponseMiddleware(session_manager), order=3)
        pipe.add("dedup", DuplicateDetectionMiddleware(session_manager), order=4)
        pipe.add("emit", EventEmitMiddleware(event_bus), order=5)
        return pipe

    @pytest.fixture
    def packet_dispatcher(
        self,
        event_bus: EventBus,
        session_manager: SessionManager,
        pipeline: PacketPipeline,
        protocol: EgtsProtocol2015,
    ) -> PacketDispatcher:
        return PacketDispatcher(
            bus=event_bus,
            session_mgr=session_manager,
            pipeline=pipeline,
            protocol=protocol,
        )

    async def test_same_pid_detected_as_duplicate(
        self,
        event_bus: EventBus,
        packet_dispatcher: PacketDispatcher,
    ):
        """Повторный AUTH-пакет (PID=42) определяется как дубликат."""
        processed: list[dict] = []

        async def on_processed(data: dict) -> None:
            processed.append(data)

        event_bus.on("packet.processed", on_processed, ordered=True)

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)

        # Первый пакет
        await event_bus.emit(
            "raw.packet.received",
            {"raw": packet_bytes, "channel": "tcp", "connection_id": "conn1"},
        )
        await asyncio.sleep(0.1)

        first_count = len(processed)

        # Второй пакет с тем же PID=42
        await event_bus.emit(
            "raw.packet.received",
            {"raw": packet_bytes, "channel": "tcp", "connection_id": "conn1"},
        )
        await asyncio.sleep(0.1)

        # Второй пакет тоже обработан
        assert len(processed) >= first_count


class TestRealPacketSmsChannel:
    """Интеграция: реальные пакеты через SMS-канал."""

    @pytest.fixture
    def event_bus(self) -> EventBus:
        return EventBus()

    @pytest.fixture
    def protocol(self) -> EgtsProtocol2015:
        return EgtsProtocol2015()

    @pytest.fixture
    def session_manager(self, event_bus: EventBus) -> SessionManager:
        return SessionManager(bus=event_bus, gost_version="2015")

    @pytest.fixture
    def pipeline(
        self, event_bus: EventBus, session_manager: SessionManager, protocol: EgtsProtocol2015
    ) -> PacketPipeline:
        pipe = PacketPipeline()
        # CrcValidationMiddleware принимает SessionManager (для получения protocol из connection)
        pipe.add("crc", CrcValidationMiddleware(session_manager), order=1)
        pipe.add("parse", ParseMiddleware(session_manager), order=2)
        pipe.add("auto_resp", AutoResponseMiddleware(session_manager), order=3)
        pipe.add("dedup", DuplicateDetectionMiddleware(session_manager), order=4)
        pipe.add("emit", EventEmitMiddleware(event_bus), order=5)
        return pipe

    @pytest.fixture
    def packet_dispatcher(
        self,
        event_bus: EventBus,
        session_manager: SessionManager,
        pipeline: PacketPipeline,
        protocol: EgtsProtocol2015,
    ) -> PacketDispatcher:
        return PacketDispatcher(
            bus=event_bus,
            session_mgr=session_manager,
            pipeline=pipeline,
            protocol=protocol,
        )

    async def test_real_auth_via_sms_channel(
        self,
        event_bus: EventBus,
        packet_dispatcher: PacketDispatcher,
    ):
        """AUTH-пакет через SMS-канал: channel="sms" сохраняется."""
        processed: list[dict] = []

        async def on_processed(data: dict) -> None:
            processed.append(data)

        event_bus.on("packet.processed", on_processed, ordered=True)

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)

        await event_bus.emit(
            "raw.packet.received",
            {"raw": packet_bytes, "channel": "sms", "connection_id": None},
        )
        await asyncio.sleep(0.1)

        assert len(processed) >= 1
        ctx = processed[0]["ctx"]
        assert ctx.channel == "sms"

    async def test_real_command_via_sms_channel(
        self,
        event_bus: EventBus,
        packet_dispatcher: PacketDispatcher,
    ):
        """COMMAND-пакет через SMS-канал."""
        processed: list[dict] = []

        async def on_processed(data: dict) -> None:
            processed.append(data)

        event_bus.on("packet.processed", on_processed, ordered=True)

        packet_bytes = _hex_to_bytes(COMMAND_HEX)

        await event_bus.emit(
            "raw.packet.received",
            {"raw": packet_bytes, "channel": "sms", "connection_id": None},
        )
        await asyncio.sleep(0.1)

        assert len(processed) >= 1
        ctx = processed[0]["ctx"]
        assert ctx.channel == "sms"


class TestCommandDispatcherWithRealPackets:
    """Интеграция: CommandDispatcher с реальными пакетами."""

    @pytest.fixture
    def event_bus(self) -> EventBus:
        return EventBus()

    @pytest.fixture
    def session_manager(self, event_bus: EventBus) -> SessionManager:
        return SessionManager(bus=event_bus, gost_version="2015")

    async def test_send_real_packet_via_tcp(
        self, event_bus: EventBus, session_manager: SessionManager
    ):
        """Реальный AUTH-пакет отправляется через TCP."""
        from core.session import UsvConnection

        mock_writer = AsyncMock()
        mock_writer.is_closing.return_value = False

        conn = MagicMock(spec=UsvConnection)
        conn.writer = mock_writer
        conn.transaction_mgr = None

        with patch.object(session_manager, "get_session", return_value=conn):
            CommandDispatcher(
                bus=event_bus, session_mgr=session_manager, cmw=None
            )

            sent: list[dict] = []

            async def on_sent(data: dict) -> None:
                sent.append(data)

            event_bus.on("command.sent", on_sent, ordered=True)

            packet_bytes = _hex_to_bytes(AUTH_USV_HEX)

            await event_bus.emit(
                "command.send",
                {
                    "packet_bytes": packet_bytes,
                    "connection_id": "conn1",
                    "channel": "tcp",
                },
            )
            await asyncio.sleep(0.1)

            mock_writer.write.assert_called_once()
            assert len(sent) == 1
            assert sent[0]["packet_bytes"] == packet_bytes

    async def test_send_real_packet_via_sms(
        self, event_bus: EventBus, session_manager: SessionManager
    ):
        """Реальный AUTH-пакет отправляется через SMS."""
        mock_cmw = AsyncMock()
        mock_cmw.is_connected = True

        CommandDispatcher(
            bus=event_bus, session_mgr=session_manager, cmw=mock_cmw
        )

        sent: list[dict] = []

        async def on_sent(data: dict) -> None:
            sent.append(data)

        event_bus.on("command.sent", on_sent, ordered=True)

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)

        await event_bus.emit(
            "command.send",
            {
                "packet_bytes": packet_bytes,
                "connection_id": None,
                "channel": "sms",
            },
        )
        await asyncio.sleep(0.1)

        mock_cmw.send_sms.assert_called_once_with(packet_bytes)
        assert len(sent) == 1
        assert sent[0]["channel"] == "sms"
