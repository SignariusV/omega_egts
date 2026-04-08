"""Тесты на enums и константы протокола EGTS

Все тестовые методы имеют явную аннотацию -> None для mypy.
"""

import enum

from libs.egts_protocol_iface.types import (
    CRC8_INIT,
    CRC8_POLY,
    CRC16_INIT,
    CRC16_POLY,
    EGTS_SL_NOT_AUTH_TO,
    MAX_PACKET_SIZE,
    MAX_RECORD_SIZE,
    MAX_SUBRECORD_SIZE,
    MIN_PACKET_SIZE,
    MIN_RECORD_SIZE,
    MIN_SUBRECORD_SIZE,
    TL_RECONNECT_TO,
    TL_RESEND_ATTEMPTS,
    TL_RESPONSE_TO,
    PacketType,
    RecordStatus,
    ResultCode,
    ServiceType,
    SubrecordType,
)


class TestPacketTypeEnum:
    """Тесты на enum PacketType"""

    def test_response_value(self) -> None:
        assert int(PacketType.RESPONSE) == 0

    def test_appdata_value(self) -> None:
        assert int(PacketType.APPDATA) == 1

    def test_signed_appdata_value(self) -> None:
        assert int(PacketType.SIGNED_APPDATA) == 2

    def test_is_intenum(self) -> None:
        assert issubclass(PacketType, enum.IntEnum)


class TestServiceTypeEnum:
    """Тесты на enum ServiceType"""

    def test_auth_value(self) -> None:
        assert int(ServiceType.AUTH) == 1

    def test_commands_value(self) -> None:
        assert int(ServiceType.COMMANDS) == 2

    def test_track_value(self) -> None:
        assert int(ServiceType.TRACK) == 3

    def test_accel_value(self) -> None:
        assert int(ServiceType.ACCEL) == 4

    def test_ecall_value(self) -> None:
        assert int(ServiceType.ECALL) == 5

    def test_firmware_value(self) -> None:
        assert int(ServiceType.FIRMWARE) == 6

    def test_is_intenum(self) -> None:
        assert issubclass(ServiceType, enum.IntEnum)


class TestSubrecordTypeEnum:
    """Тесты на enum SubrecordType"""

    def test_term_identity_value(self) -> None:
        assert int(SubrecordType.TERM_IDENTITY) == 1

    def test_auth_params_value(self) -> None:
        assert int(SubrecordType.AUTH_PARAMS) == 2

    def test_auth_info_value(self) -> None:
        assert int(SubrecordType.AUTH_INFO) == 3

    def test_result_code_value(self) -> None:
        assert int(SubrecordType.RESULT_CODE) == 4

    def test_record_response_value(self) -> None:
        assert int(SubrecordType.RECORD_RESPONSE) == 0x8000

    def test_track_data_value(self) -> None:
        assert int(SubrecordType.TRACK_DATA) == 11

    def test_accel_data_value(self) -> None:
        assert int(SubrecordType.ACCEL_DATA) == 12

    def test_command_data_value(self) -> None:
        assert int(SubrecordType.COMMAND_DATA) == 30

    def test_is_intenum(self) -> None:
        assert issubclass(SubrecordType, enum.IntEnum)


class TestRecordStatusEnum:
    """Тесты на enum RecordStatus"""

    def test_ok_value(self) -> None:
        assert int(RecordStatus.OK) == 0

    def test_error_value(self) -> None:
        assert int(RecordStatus.ERROR) == 1

    def test_unknown_service_value(self) -> None:
        assert int(RecordStatus.UNKNOWN_SERVICE) == 2

    def test_invalid_record_value(self) -> None:
        assert int(RecordStatus.INVALID_RECORD) == 3

    def test_is_intenum(self) -> None:
        assert issubclass(RecordStatus, enum.IntEnum)


class TestResultCodeEnum:
    """Тесты на enum ResultCode"""

    def test_ok_value(self) -> None:
        assert int(ResultCode.OK) == 0

    def test_in_progress_value(self) -> None:
        assert int(ResultCode.IN_PROGRESS) == 1

    def test_header_crc_error_value(self) -> None:
        assert int(ResultCode.HEADER_CRC_ERROR) == 137

    def test_data_crc_error_value(self) -> None:
        assert int(ResultCode.DATA_CRC_ERROR) == 138

    def test_auth_denied_value(self) -> None:
        assert int(ResultCode.AUTH_DENIED) == 151

    def test_id_not_found_value(self) -> None:
        assert int(ResultCode.ID_NOT_FOUND) == 153

    def test_is_intenum(self) -> None:
        assert issubclass(ResultCode, enum.IntEnum)


class TestProtocolConstants:
    """Тесты на константы протокола"""

    def test_tl_response_to(self) -> None:
        """Таймаут ожидания RESPONSE — 5 секунд"""
        assert TL_RESPONSE_TO == 5

    def test_tl_resend_attempts(self) -> None:
        """Количество повторных попыток — 3"""
        assert TL_RESEND_ATTEMPTS == 3

    def test_tl_reconnect_to(self) -> None:
        """Таймаут переподключения — 30 секунд"""
        assert TL_RECONNECT_TO == 30

    def test_egts_sl_not_auth_to(self) -> None:
        """Таймаут авторизации — 6 секунд"""
        assert EGTS_SL_NOT_AUTH_TO == 6


class TestCrcConstants:
    """Тесты на CRC-константы"""

    def test_crc8_poly(self) -> None:
        """CRC-8 полином — 0x131 (с старшим битом)"""
        assert CRC8_POLY == 0x131

    def test_crc8_init(self) -> None:
        """CRC-8 начальное значение — 0xFF"""
        assert CRC8_INIT == 0xFF

    def test_crc16_poly(self) -> None:
        """CRC-16 CCITT полином — 0x11021 (с старшим битом)"""
        assert CRC16_POLY == 0x11021

    def test_crc16_init(self) -> None:
        """CRC-16 начальное значение — 0xFFFF"""
        assert CRC16_INIT == 0xFFFF


class TestMinSizeConstants:
    """Тесты на минимальные размеры"""

    def test_min_packet_size(self) -> None:
        """Минимальный размер пакета — 11 байт"""
        assert MIN_PACKET_SIZE == 11

    def test_min_record_size(self) -> None:
        """Минимальный размер записи — 7 байт"""
        assert MIN_RECORD_SIZE == 7

    def test_min_subrecord_size(self) -> None:
        """Минимальный размер подзаписи — 3 байта"""
        assert MIN_SUBRECORD_SIZE == 3


class TestMaxSizeConstants:
    """Тесты на максимальные размеры"""

    def test_max_packet_size(self) -> None:
        assert MAX_PACKET_SIZE == 4096

    def test_max_record_size(self) -> None:
        assert MAX_RECORD_SIZE == 4096

    def test_max_subrecord_size(self) -> None:
        assert MAX_SUBRECORD_SIZE == 4096
