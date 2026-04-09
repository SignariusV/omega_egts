"""
Тесты на COMMANDS сервис EGTS (ГОСТ 33465-2015, раздел 6.7.3)

mypy: ignore-errors — тесты не типизируются (соглашение проекта).
"""

# mypy: ignore-errors
import pytest

from libs.egts_protocol_gost2015.gost2015_impl.services.commands import (
    create_command,
    create_command_response,
    create_message,
    parse_command_data,
    parse_command_details,
    serialize_command_data,
)
from libs.egts_protocol_gost2015.gost2015_impl.types import (
    EGTS_COMMAND_TYPE,
    EGTS_CONFIRMATION_TYPE,
)


class TestCommandData:
    """Тесты на подзапись COMMAND_DATA"""

    def test_command_data_build_minimal(self):
        """Сборка COMMAND_DATA (минимальная)"""
        original_data = {
            "ct": EGTS_COMMAND_TYPE.COM.value,
            "cct": 0, "cid": 1, "sid": 0,
            "acfe": False, "chsfe": False, "cd": b"",
        }
        raw = serialize_command_data(original_data)

        assert len(raw) == 10  # 1 + 4 + 4 + 1
        assert raw[0] == 0x50  # CT=5, CCT=0

        parsed_data = parse_command_data(raw)
        assert parsed_data["ct"] == 0x05
        assert parsed_data["cid"] == 1
        assert parsed_data["sid"] == 0

    def test_command_data_parse(self):
        """Парсинг COMMAND_DATA"""
        raw = b"\x50" + b"\x01\x00\x00\x00" + b"\x00\x00\x00\x00" + b"\x00"
        parsed = parse_command_data(raw)

        assert parsed["ct"] == 0x05
        assert parsed["ct_text"] == "COM"
        assert parsed["cct"] == 0
        assert parsed["cct_text"] == "OK"
        assert parsed["cid"] == 1
        assert not parsed["acfe"]
        assert not parsed["chsfe"]

    def test_command_data_with_charset(self):
        """COMMAND_DATA с кодировкой"""
        original_data = {
            "ct": 0x04, "cct": 0, "cid": 123, "sid": 0,
            "acfe": False, "chsfe": True, "chs": 0, "cd": b"Hello",
        }
        raw = serialize_command_data(original_data)
        parsed_data = parse_command_data(raw)

        assert parsed_data["chsfe"]
        assert parsed_data["chs"] == 0
        assert parsed_data["chs_text"] == "CP-1251"
        assert parsed_data["cd"] == b"Hello"

    def test_command_data_with_auth_code(self):
        """COMMAND_DATA с кодом авторизации"""
        original_data = {
            "ct": 0x05, "cct": 0, "cid": 456, "sid": 0,
            "acfe": True, "chsfe": False,
            "acl": 4, "ac": b"\x12\x34\x56\x78",
            "cd": b"\x00\x00\x01\x00",
        }
        raw = serialize_command_data(original_data)
        parsed_data = parse_command_data(raw)

        assert parsed_data["acfe"]
        assert parsed_data["ac"] == b"\x12\x34\x56\x78"
        assert parsed_data["cd"] == b"\x00\x00\x01\x00"

    def test_command_data_roundtrip(self):
        """COMMAND_DATA: туда и обратно"""
        original_data = {
            "ct": 0x05, "cct": 0, "cid": 789, "sid": 1,
            "acfe": True, "chsfe": True, "chs": 1,
            "ac": b"1234", "cd": b"\x00\x00\x02\x00\x10\x20\x30",
        }
        raw = serialize_command_data(original_data)
        parsed_data = parse_command_data(raw)

        assert parsed_data["ct"] == original_data["ct"]
        assert parsed_data["cct"] == original_data["cct"]
        assert parsed_data["cid"] == original_data["cid"]
        assert parsed_data["ac"] == original_data["ac"]
        assert parsed_data["cd"] == original_data["cd"]

    def test_command_data_invalid_size(self):
        """COMMAND_DATA: слишком маленькие данные"""
        with pytest.raises(ValueError, match="Слишком маленькие данные"):
            parse_command_data(b"\x00" * 9)


class TestCommandTypes:
    """Тесты на типы команд"""

    def test_ct_com(self):
        assert EGTS_COMMAND_TYPE(0x05).name == "COM"

    def test_ct_msgto(self):
        assert EGTS_COMMAND_TYPE(0x04).name == "MSGTO"

    def test_ct_comconf(self):
        assert EGTS_COMMAND_TYPE(0x01).name == "COMCONF"

    def test_ct_msgfrom(self):
        assert EGTS_COMMAND_TYPE(0x03).name == "MSGFROM"


class TestConfirmationTypes:
    """Тесты на типы подтверждений"""

    def test_cc_ok(self):
        assert EGTS_CONFIRMATION_TYPE(0x00).name == "OK"

    def test_cc_error(self):
        assert EGTS_CONFIRMATION_TYPE(0x01).name == "ERROR"

    def test_cc_ill(self):
        assert EGTS_CONFIRMATION_TYPE(0x02).name == "ILL"


class TestCreateCommand:
    """Тесты на создание команд"""

    def test_create_command_simple(self):
        """Создание простой команды"""
        cmd = create_command(ct=EGTS_COMMAND_TYPE.COM, cid=1, command_code=0x0001)

        assert cmd["ct"] == 0x05
        assert cmd["cid"] == 1
        assert len(cmd["cd"]) >= 5  # ADR + SZ/ACT + CCD

    def test_create_command_with_data(self):
        """Создание команды с данными"""
        cmd = create_command(
            ct=EGTS_COMMAND_TYPE.COM, cid=2, command_code=0x0002,
            address=100, action=1, data=b"\xde\xad\xbe\xef",
        )

        assert cmd["ct"] == 0x05
        assert cmd["cid"] == 2
        assert b"\xde\xad\xbe\xef" in cmd["cd"]

    def test_create_command_data_too_long(self):
        """create_command: данные > 255 байт"""
        with pytest.raises(ValueError, match="Данные команды не могут превышать 255 байт"):
            create_command(ct=EGTS_COMMAND_TYPE.COM, cid=1, command_code=0x0001, data=b"x" * 256)


class TestCreateCommandResponse:
    """Тесты на создание подтверждений команд"""

    def test_create_response_ok(self):
        """Создание подтверждения OK"""
        resp = create_command_response(cid=1, sid=0, cct=0x00)

        assert resp["ct"] == 0x01  # CT_COMCONF
        assert resp["cct"] == 0x00
        assert resp["cid"] == 1

    def test_create_response_error(self):
        """Создание подтверждения с ошибкой"""
        resp = create_command_response(cid=2, sid=1, cct=0x01, result_data=b"\x01\x02\x03")

        assert resp["ct"] == 0x01
        assert resp["cct"] == 0x01
        assert resp["cd"] == b"\x01\x02\x03"  # result_data → cd


class TestCreateMessage:
    """Тесты на создание сообщений"""

    def test_create_message_cp1251(self):
        """Создание сообщения в CP-1251"""
        msg = create_message(message="Привет", cid=1, sid=0, chs=0)

        assert msg["ct"] == 0x04  # CT_MSGTO
        assert msg["chs"] == 0
        assert msg["cd"] == "Привет".encode("cp1251")

    def test_create_message_ascii(self):
        """Создание сообщения в ASCII"""
        msg = create_message(message="Hello World", cid=2, sid=0, chs=1)

        assert msg["ct"] == 0x04
        assert msg["chs"] == 1
        assert msg["cd"] == b"Hello World"

    def test_create_message_binary_rejected(self):
        """create_message: BINARY кодировка отклоняется"""
        with pytest.raises(ValueError, match="BINARY кодировка"):
            create_message(message="test", cid=1, sid=0, chs=2)

    def test_create_message_ucs2(self):
        """Создание сообщения в UCS2 (UTF-16-LE)"""
        msg = create_message(message="Привет", cid=3, sid=0, chs=8)

        assert msg["ct"] == 0x04  # CT_MSGTO
        assert msg["chs"] == 8  # UCS2
        assert msg["cd"] == "Привет".encode("utf-16-le")

    def test_create_message_latin1(self):
        """Создание сообщения в Latin-1"""
        msg = create_message(message="Hello", cid=4, sid=0, chs=3)

        assert msg["ct"] == 0x04
        assert msg["chs"] == 3  # LATIN1
        assert msg["cd"] == b"Hello"


class TestParseCommandDetails:
    """Тесты на parse_command_details()"""

    def test_parse_command_details_gprs_apn(self):
        """Парсинг команды EGTS_GPRS_APN"""
        cd = b"\x00\x00"  # ADR=0
        cd += b"\x02"     # SZ=0, ACT=2
        cd += b"\x03\x02" # CCD=0x0203 (EGTS_GPRS_APN)
        cd += b"internet" # DT="internet"

        result = parse_command_details(cd)

        assert result["adr"] == 0
        assert result["sz"] == 0
        assert result["act"] == 2
        assert result["ccd"] == 0x0203
        assert result["dt"] == b"internet"

    def test_parse_command_details_invalid_size(self):
        """Парсинг слишком маленьких данных"""
        cd = b"\x00\x00\x00\x00"  # 4 байта (минимум 5)

        with pytest.raises(ValueError, match="Слишком маленькие данные команды"):
            parse_command_details(cd)
