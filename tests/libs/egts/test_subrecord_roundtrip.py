"""Тесты round-trip для всех парсеров подзаписей EGTS ГОСТ 33465-2015.

Каждый тест: serialize → parse → сравнение ключевых полей.
"""

from libs.egts._gost2015.subrecords import (
    RecordResponseParser,
    TermIdentityParser,
    ModuleDataParser,
    VehicleDataParser,
    AuthParamsParser,
    AuthInfoParser,
    ServiceInfoParser,
    ResultCodeParser,
    AccelDataParser,
    ServicePartDataParser,
    ServiceFullDataParser,
    CommandDataParser,
    RawMsdDataParser,
    TrackDataParser,
)
from libs.egts.types import CommandType, ConfirmationType, ActionType


class TestRecordResponseRoundtrip:
    """SRT=0 EGTS_SR_RECORD_RESPONSE."""

    def test_roundtrip_ok(self):
        parser = RecordResponseParser()
        data = {"crn": 42, "rst": 0}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["crn"] == 42
        assert parsed["rst"] == 0

    def test_roundtrip_error(self):
        parser = RecordResponseParser()
        data = {"crn": 100, "rst": 138}  # DATACRC_ERROR
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["crn"] == 100
        assert parsed["rst"] == 138


class TestTermIdentityRoundtrip:
    """SRT=1 EGTS_SR_TERM_IDENTITY."""

    def test_roundtrip_minimal(self):
        """Только TID, без опциональных полей."""
        parser = TermIdentityParser()
        data = {"tid": 12345}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["tid"] == 12345

    def test_roundtrip_full(self):
        """TID + IMEI + IMSI + MSISDN."""
        parser = TermIdentityParser()
        data = {
            "tid": 100,
            "imeie": True,
            "imei": "123456789012345",
            "imsie": True,
            "imsi": "250770000000001",
            "mne": True,
            "msisdn": "79001234567",
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["tid"] == 100
        assert parsed["imei"] == "123456789012345"
        assert parsed["imsi"] == "250770000000001"
        assert parsed["msisdn"] == "79001234567"

    def test_roundtrip_with_nid(self):
        """TID + NID (MCC+MNC)."""
        parser = TermIdentityParser()
        data = {
            "tid": 1,
            "nide": True,
            "nid": b"\xFA\x01\x4D",  # 250 77
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["tid"] == 1
        assert parsed["nid"] == b"\xFA\x01\x4D"


class TestVehicleDataRoundtrip:
    """SRT=3 EGTS_SR_VEHICLE_DATA."""

    def test_roundtrip(self):
        parser = VehicleDataParser()
        data = {
            "vin": "WBAVA71090NL12345",
            "vht": 1,  # M1
            "vpst": 1,  # бензин
        }
        serialized = parser.serialize(data)
        assert len(serialized) == 25  # 17 + 4 + 4
        parsed = parser.parse(serialized)
        assert parsed["vin"] == "WBAVA71090NL12345"
        assert parsed["vht"] == 1
        assert parsed["vpst"] == 1

    def test_roundtrip_short_vin(self):
        """VIN короче 17 символов — дополняется null."""
        parser = VehicleDataParser()
        data = {"vin": "SHORT", "vht": 0, "vpst": 0}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["vin"] == "SHORT"


class TestServiceInfoRoundtrip:
    """SRT=8 EGTS_SR_SERVICE_INFO."""

    def test_roundtrip_single_service(self):
        """Один сервис ST=10 (ECALL)."""
        parser = ServiceInfoParser()
        data = {
            "srvp": 0,
            "services": [
                {"st": 10, "sst": 0, "srvp": 0},
            ],
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert len(parsed["services"]) == 1
        assert parsed["services"][0]["st"] == 10

    def test_roundtrip_multiple_services(self):
        """Несколько сервисов."""
        parser = ServiceInfoParser()
        data = {
            "srvp": 0,
            "services": [
                {"st": 10, "sst": 0, "srvp": 0},  # ECALL
                {"st": 4, "sst": 0, "srvp": 0},   # COMMANDS
            ],
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert len(parsed["services"]) == 2
        assert parsed["services"][0]["st"] == 10
        assert parsed["services"][1]["st"] == 4

    def test_roundtrip_with_srva(self):
        """Сервис с флагом SRVA (available)."""
        parser = ServiceInfoParser()
        data = {
            "srvp": 0x80,  # SRVA=1
            "services": [
                {"st": 10, "sst": 0, "srvp": 0x80, "srva": True},
            ],
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["srva"] is True
        assert parsed["services"][0]["srva"] is True


class TestResultCodeRoundtrip:
    """SRT=9 EGTS_SR_RESULT_CODE."""

    def test_roundtrip_ok(self):
        parser = ResultCodeParser()
        data = {"rcd": 0}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["rcd"] == 0
        assert parsed["rcd_text"] == "OK"

    def test_roundtrip_auth_denied(self):
        parser = ResultCodeParser()
        data = {"rcd": 151}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["rcd"] == 151
        assert parsed["rcd_text"] == "AUTH_DENIED"


class TestAccelDataRoundtrip:
    """SRT=20 EGTS_SR_ACCEL_DATA."""

    def test_roundtrip_single_measurement(self):
        parser = AccelDataParser()
        data = {
            "atm": 1000000,
            "measurements": [
                {"rtm": 0, "xaav": 0.0, "yaav": 0.0, "zaav": 9.8},
            ],
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["sa"] == 1
        assert parsed["atm"] == 1000000
        assert len(parsed["measurements"]) == 1

    def test_roundtrip_multiple_measurements(self):
        """600 выборок (250×1мс + 350×10мс)."""
        parser = AccelDataParser()
        # Максимум 255 записей в одной подзаписи
        measurements = [
            {"rtm": i, "xaav": float(i), "yaav": float(i * 2), "zaav": 9.8}
            for i in range(255)
        ]
        data = {"atm": 1000000, "measurements": measurements}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["sa"] == 255
        assert len(parsed["measurements"]) == 255

    def test_roundtrip_negative_accel(self):
        """Отрицательные значения ускорения."""
        parser = AccelDataParser()
        data = {
            "atm": 1000000,
            "measurements": [
                {"rtm": 0, "xaav": -5.0, "yaav": -3.2, "zaav": -9.8},
            ],
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        m = parsed["measurements"][0]
        assert m["xaav"] == -5.0
        assert m["yaav"] == -3.2
        assert m["zaav"] == -9.8


class TestTrackDataRoundtrip:
    """SRT=63 EGTS_SR_TRACK_DATA."""

    def test_roundtrip_single_point(self):
        parser = TrackDataParser()
        data = {
            "atm": 1000000,
            "track_points": [
                {
                    "lat": 557558260,  # Москва
                    "lon": 376173000,
                    "spd": 60.0,
                    "sd": 180,
                    "rtm": 0,
                },
            ],
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["sa"] == 1
        assert len(parsed["track_points"]) == 1

    def test_roundtrip_70_points(self):
        """70 точек траектории (требование ТЗ п. 6.9)."""
        parser = TrackDataParser()
        points = [
            {
                "lat": 557558260 + i * 100,
                "lon": 376173000 + i * 100,
                "spd": 60.0 + i,
                "sd": 180,
                "rtm": i,
            }
            for i in range(70)
        ]
        data = {"atm": 1000000, "track_points": points}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["sa"] == 70
        assert len(parsed["track_points"]) == 70

    def test_roundtrip_no_data(self):
        """Точка без координат (TNDE=0)."""
        parser = TrackDataParser()
        data = {
            "atm": 1000000,
            "track_points": [
                {"tnde": False, "rtm": 0},
            ],
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["sa"] == 1
        assert len(parsed["track_points"]) == 1


class TestRawMsdDataRoundtrip:
    """SRT=62 EGTS_SR_RAW_MSD_DATA."""

    def test_roundtrip(self):
        parser = RawMsdDataParser()
        msd_payload = b"\x01\x02\x03\x04\x05"
        data = {"fm": 1, "msd": msd_payload}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["fm"] == 1
        assert parsed["msd"] == msd_payload
        assert parsed["msd_len"] == 5

    def test_roundtrip_bytes_input(self):
        """Сериализация из bytes напрямую."""
        parser = RawMsdDataParser()
        raw = b"\x01\x02\x03\x04"
        serialized = parser.serialize(raw)
        assert serialized == raw


class TestServicePartDataRoundtrip:
    """SRT=33 EGTS_SR_SERVICE_PART_DATA."""

    def test_roundtrip_first_part(self):
        """Первая часть с ODH (ODH: 7 байт header + null-terminated filename)."""
        parser = ServicePartDataParser()
        # Парсер ищет null начиная с offset+7, поэтому ODH должен быть >= 8 байт
        # с null-терминатором на позиции >= 7
        odh = b"\x01\x3F\x00\x01\x00\x00\x00\x00"  # 8 байт, байт[7] = null
        data = {
            "id": 1,
            "pn": 1,
            "epq": 3,
            "odh": odh,
            "od": b"\xAA\xBB\xCC",
        }
        serialized = parser.serialize(data)
        # serialized = header(6) + odh(8) + od(3) = 17 байт
        # parse: offset=6, ищет null с позиции 13. raw[13] = odh[7] = 0x00
        parsed = parser.parse(serialized)
        assert parsed["id"] == 1
        assert parsed["pn"] == 1
        assert parsed["epq"] == 3
        assert parsed["od"] == b"\xAA\xBB\xCC"

    def test_roundtrip_middle_part(self):
        """Средняя часть без ODH."""
        parser = ServicePartDataParser()
        data = {
            "id": 1,
            "pn": 2,
            "epq": 3,
            "od": b"\xDD\xEE\xFF",
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["pn"] == 2
        assert parsed["od"] == b"\xDD\xEE\xFF"


class TestServiceFullDataRoundtrip:
    """SRT=34 EGTS_SR_SERVICE_FULL_DATA."""

    def test_roundtrip(self):
        """ODH с null-терминатором (парсер ищет null начиная с позиции 7)."""
        parser = ServiceFullDataParser()
        # ODH должен содержать null-терминатор на позиции >= 7
        odh = b"\x01\x3F\x00\x01\x00\x00\x00\x00"  # 8 байт, raw[7] = null
        data = {
            "odh": odh,
            "od": b"\x01\x02\x03\x04\x05",
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["od"] == b"\x01\x02\x03\x04\x05"


class TestModuleDataRoundtrip:
    """SRT=2 EGTS_SR_MODULE_DATA."""

    def test_roundtrip(self):
        parser = ModuleDataParser()
        data = {
            "mt": 1,
            "vid": 12345,
            "fwv": 100,
            "swv": 200,
            "md": 0,
            "st": 1,
            "srn": "SN12345",
            "dscr": "Test module",
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["mt"] == 1
        assert parsed["vid"] == 12345
        assert parsed["srn"] == "SN12345"
        assert parsed["dscr"] == "Test module"


class TestAuthParamsRoundtrip:
    """SRT=6 EGTS_SR_AUTH_PARAMS."""

    def test_roundtrip_no_encryption(self):
        """Без шифрования — только FLG=0."""
        parser = AuthParamsParser()
        data = {"flg": 0}
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["flg"] == 0
        assert parsed["ena"] is False


class TestAuthInfoRoundtrip:
    """SRT=7 EGTS_SR_AUTH_INFO."""

    def test_roundtrip(self):
        parser = AuthInfoParser()
        data = {
            "unm": "user123",
            "upsw": "password",
        }
        serialized = parser.serialize(data)
        parsed = parser.parse(serialized)
        assert parsed["unm"] == "user123"
        assert parsed["upsw"] == "password"


class TestCommandCodesCompleteness:
    """Тесты на полноту COMMAND_CODES."""

    def test_all_required_codes_present(self):
        """Все коды из ТЗ присутствуют в COMMAND_CODES."""
        from libs.egts.types import COMMAND_CODES

        required = {
            0x0101: "EGTS_GPRS_APN",
            0x0102: "EGTS_SERVER_ADDRESS",
            0x0114: "EGTS_ACCEL_DATA",
            0x0115: "EGTS_TRACK_DATA",
            0x0404: "EGTS_UNIT_ID",
            0x0405: "EGTS_UNIT_IMEI",
            0x0501: "EGTS_UNIT_MIC_LEVEL",
            0x0502: "EGTS_UNIT_SPK_LEVEL",
        }
        for code, name in required.items():
            assert code in COMMAND_CODES, f"Missing {name} (0x{code:04X})"
            assert COMMAND_CODES[code] == name

    def test_ecall_params_present(self):
        """Параметры eCall из Таблицы 47."""
        from libs.egts.types import COMMAND_CODES

        ecall_codes = [
            0x020D,  # EGTS_ECALL_TEST_NUMBER
            0x0210,  # EGTS_ECALL_ON
            0x0230,  # EGTS_VEHICLE_VIN
            0x0231,  # EGTS_VEHICLE_TYPE
            0x0232,  # EGTS_VEHICLE_PROPULSION_STORAGE_TYPE
        ]
        for code in ecall_codes:
            assert code in COMMAND_CODES, f"Missing eCall code 0x{code:04X}"
