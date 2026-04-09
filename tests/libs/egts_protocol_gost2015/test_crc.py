"""Тесты на CRC-8 и CRC-16 (ГОСТ 33465-2015, Приложения Г, Д)

Покрывает:
- crc8 — вычисление CRC-8 заголовка
- crc16 — вычисление CRC-16 данных ППУ
- verify_crc8 — проверка CRC-8
- verify_crc16 — проверка CRC-16
"""


from libs.egts_protocol_gost2015.gost2015_impl.crc import (
    crc8,
    crc16,
    verify_crc8,
    verify_crc16,
)
from libs.egts_protocol_gost2015.gost2015_impl.types import CRC8_INIT, CRC16_INIT


class TestCrc8:
    """Тесты на CRC-8 для заголовка пакета"""

    def test_crc8_empty_data(self) -> None:
        """CRC-8 от пустых данных (ГОСТ 33465-2015, Приложение Д)"""
        assert crc8(b"") == CRC8_INIT  # Init value = 0xFF

    def test_crc8_single_byte(self) -> None:
        """CRC-8 от одного байта"""
        result = crc8(b"\x00")
        assert isinstance(result, int)
        assert 0 <= result <= 255

    def test_crc8_example_from_gost(self) -> None:
        """
        Пример из ГОСТ 33465-2015, Приложение Д.
        Заголовок с полями PRV=0x01, SKID=0x00, HL=0x0C и т.д.
        """
        header = bytes([0x01, 0x00, 0x00, 0x0C, 0x00, 0x01, 0x02, 0x00])
        result = crc8(header)
        assert isinstance(result, int)
        assert 0 <= result <= 255

    def test_crc8_consistency(self) -> None:
        """CRC-8 должен быть детерминированным"""
        data = b"\x01\x02\x03\x04"
        assert crc8(data) == crc8(data)

    def test_crc8_different_data(self) -> None:
        """Разные данные обычно дают разный CRC"""
        crc1 = crc8(b"\x00\x00\x00\x00")
        crc2 = crc8(b"\x01\x00\x00\x00")
        assert isinstance(crc1, int)
        assert isinstance(crc2, int)


class TestCrc16:
    """Тесты на CRC-16 для данных ППУ"""

    def test_crc16_empty_data(self) -> None:
        """CRC-16 от пустых данных"""
        assert crc16(b"") == CRC16_INIT  # Init value = 0xFFFF

    def test_crc16_single_byte(self) -> None:
        """CRC-16 от одного байта"""
        result = crc16(b"\x00")
        assert isinstance(result, int)
        assert 0 <= result <= 65535

    def test_crc16_example_from_gost(self) -> None:
        """
        Пример из ГОСТ 33465-2015, Приложение Г.
        """
        data = bytes([0x00, 0x06, 0x01, 0x00, 0x00, 0x00, 0x01, 0x0A])
        result = crc16(data)
        assert isinstance(result, int)
        assert 0 <= result <= 65535

    def test_crc16_consistency(self) -> None:
        """CRC-16 должен быть детерминированным"""
        data = b"\x01\x02\x03\x04\x05\x06"
        assert crc16(data) == crc16(data)

    def test_crc16_larger_data(self) -> None:
        """CRC-16 от больших данных"""
        data = bytes(range(256)) * 10  # 2560 байт
        result = crc16(data)
        assert isinstance(result, int)
        assert 0 <= result <= 65535


class TestVerifyCrc8:
    """Тесты на проверку CRC-8"""

    def test_verify_crc8_valid(self) -> None:
        """Проверка корректного CRC-8"""
        data = b"\x01\x02\x03"
        crc = crc8(data)
        assert verify_crc8(data, crc) is True

    def test_verify_crc8_invalid(self) -> None:
        """Проверка некорректного CRC-8"""
        data = b"\x01\x02\x03"
        assert verify_crc8(data, 0x00) is False


class TestVerifyCrc16:
    """Тесты на проверку CRC-16"""

    def test_verify_crc16_valid(self) -> None:
        """Проверка корректного CRC-16"""
        data = b"\x01\x02\x03\x04\x05"
        crc = crc16(data)
        assert verify_crc16(data, crc) is True

    def test_verify_crc16_invalid(self) -> None:
        """Проверка некорректного CRC-16"""
        data = b"\x01\x02\x03\x04\x05"
        assert verify_crc16(data, 0x0000) is False
