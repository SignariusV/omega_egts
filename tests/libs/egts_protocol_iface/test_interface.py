"""Тесты на IEgtsProtocol интерфейс и factory функцию

Все тестовые методы имеют явную аннотацию -> None для mypy.
"""

import pytest

from libs.egts_protocol_iface import IEgtsProtocol, create_protocol


class TestIEgtsProtocol:
    """Тесты на интерфейс IEgtsProtocol"""

    def test_protocol_has_required_methods(self) -> None:
        """IEgtsProtocol определяет все требуемые методы"""
        required_methods = [
            "parse_packet",
            "parse_sms_pdu",
            "build_response",
            "build_record_response",
            "build_packet",
            "build_sms_pdu",
            "validate_crc8",
            "validate_crc16",
            "calculate_crc8",
            "calculate_crc16",
        ]
        for method_name in required_methods:
            assert hasattr(IEgtsProtocol, method_name), (
                f"Метод {method_name} не определён в IEgtsProtocol"
            )

    def test_protocol_has_version_property(self) -> None:
        """IEgtsProtocol имеет свойство version"""
        assert hasattr(IEgtsProtocol, "version")

    def test_protocol_has_capabilities_property(self) -> None:
        """IEgtsProtocol имеет свойство capabilities"""
        assert hasattr(IEgtsProtocol, "capabilities")

    def test_runtime_checkable(self) -> None:
        """IEgtsProtocol помечен как runtime_checkable"""
        from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015

        proto = EgtsProtocol2015()
        assert isinstance(proto, IEgtsProtocol)


class TestCreateProtocol:
    """Тесты на factory функцию create_protocol"""

    def test_unknown_version_raises(self) -> None:
        """Неизвестная версия ГОСТ вызывает ValueError"""
        with pytest.raises(ValueError, match="Неподдерживаемая версия"):
            create_protocol("1999")

    def test_2015_returns_instance(self) -> None:
        """ГОСТ 2015 — возвращает экземпляр (заглушка)"""
        protocol = create_protocol("2015")
        assert protocol.version == "2015"
        assert protocol.capabilities == {"sms_pdu"}
        # Методы пока бросают NotImplementedError
        with pytest.raises(NotImplementedError):
            protocol.parse_packet(b"")

    def test_2023_raises_not_implemented(self) -> None:
        """ГОСТ 2023 — NotImplementedError (ещё не реализован)"""
        with pytest.raises(NotImplementedError):
            create_protocol("2023")
