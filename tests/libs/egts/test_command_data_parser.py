"""Тесты для CommandDataParser с поддержкой структурированного CD."""

from libs.egts._gost2015.subrecords import CommandDataParser
from libs.egts.types import CommandType, ConfirmationType, ActionType


class TestCommandDataParserParse:
    """Тесты парсинга COMMAND_DATA согласно ГОСТ 33465-2015."""

    def test_parse_minimal(self):
        """Минимальный пакет COMMAND_DATA."""
        raw = bytes([
            0x10,  # CT=1 (COMCONF), CCT=0 (OK)
            # CID=0 (4 байта)
            0x00, 0x00, 0x00, 0x00,
            # SID=0 (4 байта)
            0x00, 0x00, 0x00, 0x00,
            # Flags: ACFE=0, CHSFE=0
            0x00,
        ])

        parser = CommandDataParser()
        result = parser.parse(raw)

        assert result["ct"] == CommandType.COMCONF
        assert result["cct"] == ConfirmationType.OK
        assert result["cid"] == 0
        assert result["sid"] == 0
        assert result["acfe"] is False
        assert result["chsfe"] is False
        assert result["chs"] is None
        assert result["cd"] == b""  # Пустой CD

    def test_parse_with_auth_code(self):
        """COMMAND_DATA с кодом авторизации."""
        raw = bytes([
            0x50,  # CT=5 (COM), CCT=0
            # CID=123 (4 байта)
            0x7B, 0x00, 0x00, 0x00,
            # SID=456 (4 байта)
            0xC8, 0x01, 0x00, 0x00,
            # Flags: ACFE=1, CHSFE=0
            0x80,
            # ACL=6
            0x06,
            # AC="SECRET"
            0x53, 0x45, 0x43, 0x52, 0x45, 0x54,
        ])

        parser = CommandDataParser()
        result = parser.parse(raw)

        assert result["ct"] == CommandType.COM
        assert result["cct"] == 0
        assert result["cid"] == 123
        assert result["sid"] == 456
        assert result["acfe"] is True
        assert result["acl"] == 6
        assert result["ac"] == b"SECRET"

    def test_parse_ct_com_with_cd(self):
        """CT_COM (5) с данными CD (таблица 30)."""
        # ADR=0, ACT=0 (PARAMS), CCD=0x0101 (EGTS_GPRS_APN), DT="internet"
        dt = b"internet"
        cd_data = (
            b"\x00\x00"          # ADR=0
            + bytes([0x00])     # ACT=0, SZ=0
            + b"\x01\x01"      # CCD=0x0101
            + dt
        )

        raw = bytes([
            0x50,  # CT=5 (COM), CCT=0
            # CID=0, SID=0
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            # Flags: ACFE=0, CHSFE=0
            0x00,
        ]) + cd_data

        parser = CommandDataParser()
        result = parser.parse(raw)

        assert result["ct"] == CommandType.COM
        assert isinstance(result["cd"], dict)

        cd = result["cd"]
        assert cd["adr"] == 0
        assert cd["act"] == ActionType.PARAMS
        assert cd["ccd"] == 0x0101  # EGTS_GPRS_APN
        assert "GPRS_APN" in cd["ccd_text"]
        # dt is now returned as string (decoded from cp1251)
        assert cd["dt"] == dt.decode("cp1251")

    def test_parse_ct_comconf_with_cd(self):
        """CT_COMCONF (1) с данными CD (таблица 31)."""
        # ADR=0, CCD=0x0102 (EGTS_SERVER_ADDRESS), DT="10.20.2.171:9090"
        dt = b"10.20.2.171:9090"
        cd_data = (
            b"\x00\x00"          # ADR=0
            + b"\x02\x01"      # CCD=0x0102
            + dt
        )

        raw = bytes([
            0x10,  # CT=1 (COMCONF), CCT=0 (OK)
            # CID=0, SID=0
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            # Flags: ACFE=0, CHSFE=0
            0x00,
        ]) + cd_data

        parser = CommandDataParser()
        result = parser.parse(raw)

        assert result["ct"] == CommandType.COMCONF
        assert isinstance(result["cd"], dict)

        cd = result["cd"]
        assert cd["adr"] == 0
        assert cd["ccd"] == 0x0102  # EGTS_SERVER_ADDRESS
        assert "SERVER_ADDRESS" in cd["ccd_text"]
        # dt is now returned as string (decoded from cp1251)
        assert cd["dt"] == dt.decode("cp1251")


class TestCommandDataParserSerialize:
    """Тесты сериализации COMMAND_DATA согласно ГОСТ 33465-2015."""

    def test_serialize_minimal(self):
        """Сериализация минимального пакета."""
        data = {
            "ct": CommandType.COMCONF,
            "cct": ConfirmationType.OK,
            "cid": 0,
            "sid": 0,
            "acfe": False,
            "chsfe": False,
            "cd": b"",
        }

        parser = CommandDataParser()
        result = parser.serialize(data)

        # Проверяем что можем распарсить обратно
        parsed = parser.parse(result)
        assert parsed["ct"] == CommandType.COMCONF
        assert parsed["cct"] == ConfirmationType.OK

    def test_serialize_with_auth_code(self):
        """Сериализация с кодом авторизации."""
        data = {
            "ct": CommandType.COM,
            "cct": 0,
            "cid": 123,
            "sid": 456,
            "acfe": True,
            "chsfe": False,
            "acl": 6,
            "ac": b"SECRET",
            "cd": b"",
        }

        parser = CommandDataParser()
        result = parser.serialize(data)
        parsed = parser.parse(result)

        assert parsed["ct"] == CommandType.COM
        assert parsed["cid"] == 123
        assert parsed["acfe"] is True
        assert parsed["ac"] == b"SECRET"

    def test_serialize_ct_com_with_dict_cd(self):
        """Сериализация CT_COM с CD в виде dict."""
        data = {
            "ct": CommandType.COM,
            "cct": 0,
            "cid": 0,
            "sid": 0,
            "acfe": False,
            "chsfe": False,
            "cd": {
                "adr": 0,
                "act": ActionType.PARAMS,
                "sz": 0,
                "ccd": 0x0101,  # EGTS_GPRS_APN
                "dt": "internet",  # String, will be encoded to cp1251
            },
        }

        parser = CommandDataParser()
        result = parser.serialize(data)
        parsed = parser.parse(result)

        assert parsed["ct"] == CommandType.COM
        cd = parsed["cd"]
        assert isinstance(cd, dict)
        assert cd["adr"] == 0
        assert cd["act"] == ActionType.PARAMS
        assert cd["ccd"] == 0x0101
        # After roundtrip, dt is a string (decoded from cp1251)
        assert cd["dt"] == "internet"

    def test_serialize_ct_comconf_with_dict_cd(self):
        """Сериализация CT_COMCONF с CD в виде dict."""
        data = {
            "ct": CommandType.COMCONF,
            "cct": ConfirmationType.OK,
            "cid": 0,
            "sid": 0,
            "acfe": False,
            "chsfe": False,
            "cd": {
                "adr": 0,
                "ccd": 0x0102,  # EGTS_SERVER_ADDRESS
                "dt": "10.20.2.171:9090",  # String, will be encoded to cp1251
            },
        }

        parser = CommandDataParser()
        result = parser.serialize(data)
        parsed = parser.parse(result)

        assert parsed["ct"] == CommandType.COMCONF
        cd = parsed["cd"]
        assert isinstance(cd, dict)
        assert cd["adr"] == 0
        assert cd["ccd"] == 0x0102
        # After roundtrip, dt is a string (decoded from cp1251)
        assert cd["dt"] == "10.20.2.171:9090"


class TestCommandDataRoundtrip:
    """Тесты на полный цикл serialize -> parse."""

    def test_roundtrip_comconf(self):
        """Roundtrip для CT_COMCONF."""
        original = {
            "ct": CommandType.COMCONF,
            "cct": ConfirmationType.OK,
            "cid": 42,
            "sid": 100,
            "acfe": True,
            "chsfe": True,
            "chs": 0,  # CP-1251
            "acl": 6,
            "ac": b"MYCODE",
            "cd": {
                "adr": 0,
                "ccd": 0x0102,
                "dt": b"server:9090",
            },
        }

        parser = CommandDataParser()
        serialized = parser.serialize(original)
        parsed = parser.parse(serialized)

        assert parsed["ct"] == original["ct"]
        assert parsed["cct"] == original["cct"]
        assert parsed["cid"] == original["cid"]
        assert parsed["sid"] == original["sid"]
        assert parsed["cd"]["adr"] == original["cd"]["adr"]
        assert parsed["cd"]["ccd"] == original["cd"]["ccd"]

    def test_roundtrip_com(self):
        """Roundtrip для CT_COM."""
        original = {
            "ct": CommandType.COM,
            "cct": 0,
            "cid": 1,
            "sid": 2,
            "acfe": False,
            "chsfe": False,
            "cd": {
                "adr": 5,
                "act": ActionType.SET,
                "sz": 0,
                "ccd": 0x0103,  # EGTS_SIM_PIN
                "dt": b"1234",
            },
        }

        parser = CommandDataParser()
        serialized = parser.serialize(original)
        parsed = parser.parse(serialized)

        assert parsed["ct"] == original["ct"]
        assert parsed["cd"]["adr"] == 5
        assert parsed["cd"]["act"] == ActionType.SET
        assert parsed["cd"]["ccd"] == 0x0103
