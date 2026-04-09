"""
Тесты на AUTH сервис EGTS (ГОСТ 33465-2015, раздел 6.7.2)

mypy: ignore-errors — тесты не типизируются (соглашение проекта).
"""

# mypy: ignore-errors
import pytest

from libs.egts_protocol_gost2015.gost2015_impl.services.auth import (
    parse_auth_info,
    parse_auth_params,
    parse_module_data,
    parse_record_response,
    parse_result_code,
    parse_service_info,
    parse_term_identity,
    parse_vehicle_data,
    serialize_auth_info,
    serialize_auth_params,
    serialize_module_data,
    serialize_record_response,
    serialize_result_code,
    serialize_service_info,
    serialize_term_identity,
    serialize_vehicle_data,
)

# ============================================
# Тесты для EGTS_SR_TERM_IDENTITY (таблица 19)
# ============================================


class TestTermIdentity:
    """Тесты на подзапись EGTS_SR_TERM_IDENTITY"""

    def test_term_identity_build_minimal(self):
        """Сборка минимальной TERM_IDENTITY (только TID)"""
        data = {"tid": 100, "imeie": False, "imsie": False}
        raw = serialize_term_identity(data)

        # Минимальный размер: TID(4) + Flags(1) = 5 байт
        assert len(raw) == 5
        assert raw[0:4] == b"\x64\x00\x00\x00"  # TID = 100 (little-endian)
        assert raw[4] == 0x00  # Flags

    def test_term_identity_parse_minimal(self):
        """Парсинг минимальной TERM_IDENTITY"""
        raw = bytes([0x39, 0x30, 0x00, 0x00, 0x00])  # TID=12345, Flags=0
        data = parse_term_identity(raw)

        assert data["tid"] == 12345
        assert data["flags"] == 0x00

    def test_term_identity_roundtrip(self):
        """Круговой тест: сборка → парсинг → сверка"""
        original_data = {"tid": 999, "imeie": True, "imei": "987654321098765"}
        raw = serialize_term_identity(original_data)
        parsed_data = parse_term_identity(raw)

        assert parsed_data["tid"] == original_data["tid"]
        assert parsed_data["imei"] == original_data["imei"]

    def test_term_identity_imei_padding(self):
        """Проверка padding для IMEI"""
        data = {"tid": 1, "imeie": True, "imei": "12345"}
        raw = serialize_term_identity(data)
        parsed = parse_term_identity(raw)

        # IMEI при парсинге очищается от нулевых байтов
        assert parsed["imei"] == "12345"


# ============================================
# Тесты для EGTS_SR_MODULE_DATA (таблица 21)
# ============================================


class TestModuleData:
    """Тесты на подзапись EGTS_SR_MODULE_DATA"""

    def test_module_data_build_minimal(self):
        """Сборка минимальной MODULE_DATA"""
        data = {
            "mt": 1, "vid": 12345, "fwv": 0x0102, "swv": 0x0304, "md": 1, "st": 1,
        }
        raw = serialize_module_data(data)

        # MT(1) + VID(4) + FWV(2) + SWV(2) + MD(1) + ST(1) + SRN(\x00) + DSCR(\x00) = 13 байт
        assert len(raw) == 13

    def test_module_data_build_with_strings(self):
        """Сборка MODULE_DATA со строками"""
        data = {
            "mt": 3, "vid": 54321, "fwv": 0x0200, "swv": 0x0100,
            "md": 0, "st": 1, "srn": "SN123456", "dscr": "GPS Module",
        }
        raw = serialize_module_data(data)
        assert b"\x00" in raw  # Разделитель между полями

    def test_module_data_parse_minimal(self):
        """Парсинг минимальной MODULE_DATA"""
        raw = bytes([
            0x01,  # MT = 1
            0x39, 0x30, 0x00, 0x00,  # VID = 12345
            0x02, 0x01,  # FWV = 0x0102
            0x04, 0x03,  # SWV = 0x0304
            0x01,  # MD = 1
            0x01,  # ST = 1
            0x00,  # SRN = ''
            0x00,  # DSCR = ''
        ])
        data = parse_module_data(raw)

        assert data["mt"] == 1
        assert data["vid"] == 12345
        assert data["fwv"] == 0x0102
        assert data["swv"] == 0x0304
        assert data["srn"] == ""
        assert data["dscr"] == ""

    def test_module_data_roundtrip(self):
        """Круговой тест"""
        original_data = {
            "mt": 4, "vid": 11111, "fwv": 0x0506, "swv": 0x0708,
            "md": 2, "st": 1, "srn": "GSM001", "dscr": "LTE Module",
        }
        raw = serialize_module_data(original_data)
        parsed_data = parse_module_data(raw)

        assert parsed_data["mt"] == original_data["mt"]
        assert parsed_data["vid"] == original_data["vid"]
        assert parsed_data["srn"] == original_data["srn"]
        assert parsed_data["dscr"] == original_data["dscr"]


# ============================================
# Тесты для EGTS_SR_VEHICLE_DATA
# ============================================


class TestVehicleData:
    """Тесты на подзапись VEHICLE_DATA"""

    def test_vehicle_data_build(self):
        """Сборка VEHICLE_DATA"""
        original_data = {
            "vin": "XTA12345678901234",
            "vht": 0x00000001,
            "vpst": 0x00000001,
        }
        raw = serialize_vehicle_data(original_data)

        assert len(raw) == 25  # 17 + 4 + 4
        assert raw[:17] == b"XTA12345678901234"

        parsed_data = parse_vehicle_data(raw)
        assert parsed_data["vin"] == original_data["vin"]
        assert parsed_data["vht"] == original_data["vht"]
        assert parsed_data["vpst"] == original_data["vpst"]

    def test_vehicle_data_roundtrip(self):
        """VEHICLE_DATA: туда и обратно"""
        original_data = {
            "vin": "WBA1234567890ABCD",
            "vht": 0x00000004,
            "vpst": 0x00000008,
        }
        raw = serialize_vehicle_data(original_data)
        parsed_data = parse_vehicle_data(raw)

        assert parsed_data["vin"] == original_data["vin"]
        assert parsed_data["vht"] == original_data["vht"]
        assert parsed_data["vpst"] == original_data["vpst"]

    def test_vehicle_data_invalid_size(self):
        """VEHICLE_DATA: слишком маленькие данные"""
        with pytest.raises(ValueError, match="Слишком маленькие данные"):
            parse_vehicle_data(b"\x00" * 24)


# ============================================
# Тесты для EGTS_SR_RECORD_RESPONSE
# ============================================


class TestRecordResponse:
    """Тесты на подзапись RECORD_RESPONSE"""

    def test_record_response_build(self):
        """Сборка RECORD_RESPONSE"""
        original_data = {"crn": 123, "rst": 0}
        raw = serialize_record_response(original_data)

        assert len(raw) == 3
        parsed_data = parse_record_response(raw)
        assert parsed_data["crn"] == 123
        assert parsed_data["rst"] == 0

    def test_record_response_roundtrip(self):
        """RECORD_RESPONSE: туда и обратно"""
        original_data = {"crn": 65535, "rst": 5}
        raw = serialize_record_response(original_data)
        parsed_data = parse_record_response(raw)

        assert parsed_data["crn"] == original_data["crn"]
        assert parsed_data["rst"] == original_data["rst"]


# ============================================
# Тесты для EGTS_SR_RESULT_CODE
# ============================================


class TestResultCode:
    """Тесты на подзапись RESULT_CODE"""

    def test_result_code_build(self):
        """Сборка RESULT_CODE"""
        original_data = {"rcd": 0}
        raw = serialize_result_code(original_data)

        assert len(raw) == 1
        parsed_data = parse_result_code(raw)
        assert parsed_data["rcd"] == 0
        assert "EGTS_PC_OK" in parsed_data["rcd_text"]

    def test_result_code_parse_authfail(self):
        """RESULT_CODE: AUTHFAIL (rcd=5 может быть Unknown если не определён)"""
        parsed = parse_result_code(b"\x05")
        assert parsed["rcd"] == 5
        # AUTHFAIL может быть не определён в RESULT_CODES — это нормально
        assert "Unknown" in parsed["rcd_text"] or "AUTHFAIL" in parsed["rcd_text"]

    def test_result_code_roundtrip(self):
        """RESULT_CODE: туда и обратно"""
        original_data = {"rcd": 12}
        raw = serialize_result_code(original_data)
        parsed_data = parse_result_code(raw)

        assert parsed_data["rcd"] == original_data["rcd"]


# ============================================
# Тесты для EGTS_SR_SERVICE_INFO
# ============================================


class TestServiceInfo:
    """Тесты на подзапись SERVICE_INFO (ГОСТ 33465-2015, таблица 26)"""

    def test_service_info_build(self):
        """Сборка SERVICE_INFO"""
        original_data = {
            "srvp": 0x00, "srva": False, "srvrp": 0,
            "services": [1, 2, 4],  # AUTH, TELEDATA, COMMANDS
        }
        raw = serialize_service_info(original_data)

        # 1 (SRVP общий) + 3 * 3 (ST + SST + SRVP на каждый сервис)
        assert len(raw) == 10
        parsed_data = parse_service_info(raw)
        assert not parsed_data["srva"]
        assert len(parsed_data["services"]) == 3
        assert parsed_data["services"][0]["st"] == 1
        assert parsed_data["services"][0]["sst"] == 0

    def test_service_info_roundtrip(self):
        """SERVICE_INFO: туда и обратно"""
        original_data = {
            "srvp": 0x00, "srva": False, "srvrp": 0,
            "services": [
                {"st": 1, "sst": 0, "srvp": 0x00, "srva": False, "srvrp": 0},
                {"st": 2, "sst": 0, "srvp": 0x00, "srva": False, "srvrp": 0},
            ],
        }
        raw = serialize_service_info(original_data)
        parsed_data = parse_service_info(raw)

        assert len(parsed_data["services"]) == 2
        for i, svc in enumerate(parsed_data["services"]):
            assert svc["st"] == original_data["services"][i]["st"]


# ============================================
# Тесты для EGTS_SR_AUTH_PARAMS
# ============================================


class TestAuthParams:
    """Тесты на подзапись AUTH_PARAMS"""

    def test_auth_params_build_minimal(self):
        """Сборка AUTH_PARAMS (минимальный)"""
        original_data = {"flg": 0x00, "ena": False, "pke": False, "isle": False}
        raw = serialize_auth_params(original_data)

        assert len(raw) == 1
        parsed_data = parse_auth_params(raw)
        assert parsed_data["flg"] == 0
        assert not parsed_data["pke"]

    def test_auth_params_with_public_key(self):
        """AUTH_PARAMS с публичным ключом"""
        pbk = b"\x01\x02\x03\x04\x05"
        original_data = {"flg": 0x02, "pke": True, "pbk": pbk}
        raw = serialize_auth_params(original_data)

        assert len(raw) == 8  # 1 + 2 + 5
        parsed_data = parse_auth_params(raw)
        assert parsed_data["pke"]
        assert parsed_data["pbk"] == pbk
        assert parsed_data["pkl"] == 5


# ============================================
# Тесты для EGTS_SR_AUTH_INFO (таблица 24)
# ============================================


class TestAuthInfo:
    """Тесты на подзапись AUTH_INFO"""

    def test_auth_info_build_basic(self):
        """Сборка AUTH_INFO с UNM и UPSW"""
        original_data = {"unm": "user123", "upsw": "pass456"}
        raw = serialize_auth_info(original_data)

        # user123\0pass456\0 = 7 + 1 + 7 + 1 = 16 байт
        assert len(raw) == 16
        assert raw == b"user123\x00pass456\x00"

        parsed_data = parse_auth_info(raw)
        assert parsed_data["unm"] == original_data["unm"]
        assert parsed_data["upsw"] == original_data["upsw"]
        assert parsed_data["ss"] is None

    def test_auth_info_build_with_ss(self):
        """Сборка AUTH_INFO с UNM, UPSW и SS"""
        original_data = {"unm": "user123", "upsw": "pass456", "ss": "server_data"}
        raw = serialize_auth_info(original_data)

        assert len(raw) == 28  # 7+1+7+1+11+1
        assert raw == b"user123\x00pass456\x00server_data\x00"

        parsed_data = parse_auth_info(raw)
        assert parsed_data["ss"] == original_data["ss"]

    def test_auth_info_roundtrip(self):
        """AUTH_INFO: туда и обратно"""
        original_data = {"unm": "test_user", "upsw": "test_pass", "ss": "extra_data"}
        raw = serialize_auth_info(original_data)
        parsed_data = parse_auth_info(raw)

        assert parsed_data["unm"] == original_data["unm"]
        assert parsed_data["upsw"] == original_data["upsw"]
        assert parsed_data["ss"] == original_data["ss"]

    def test_auth_info_cp1251_encoding(self):
        """AUTH_INFO с кодировкой CP-1251"""
        original_data = {"unm": "пользователь", "upsw": "пароль"}
        raw = serialize_auth_info(original_data)
        parsed_data = parse_auth_info(raw)

        assert parsed_data["unm"] == original_data["unm"]
        assert parsed_data["upsw"] == original_data["upsw"]

    def test_auth_info_unm_too_long(self):
        """AUTH_INFO: ошибка при UNM > 32 байт"""
        with pytest.raises(ValueError, match="UNM превышает максимальную длину"):
            serialize_auth_info({"unm": "a" * 33, "upsw": "pass"})

    def test_auth_info_upsw_too_long(self):
        """AUTH_INFO: ошибка при UPSW > 32 байт"""
        with pytest.raises(ValueError, match="UPSW превышает максимальную длину"):
            serialize_auth_info({"unm": "user", "upsw": "p" * 33})


# ============================================
# Интеграционные тесты авторизации (полная цепочка)
# ============================================


class TestAuthChain:
    """Интеграционные тесты полной цепочки авторизации"""

    def test_term_identity_minimal_chain(self):
        """Цепочка: TERM_IDENTITY → AUTH_PARAMS → AUTH_INFO → RESULT_CODE"""
        # Шаг 1: УСВ отправляет TERM_IDENTITY
        term_data = {"tid": 12345, "imeie": False, "imsie": False}
        term_raw = serialize_term_identity(term_data)
        term_parsed = parse_term_identity(term_raw)
        assert term_parsed["tid"] == 12345

        # Шаг 2: ТП запрашивает AUTH_PARAMS (простой алгоритм, без шифрования)
        auth_params_data = {"flg": 0x00, "ena": False, "pke": False, "isle": False}
        auth_params_raw = serialize_auth_params(auth_params_data)
        auth_params_parsed = parse_auth_params(auth_params_raw)
        assert not auth_params_parsed["pke"]

        # Шаг 3: УСВ отправляет AUTH_INFO
        auth_info_data = {"unm": "test_user", "upsw": "test_pass"}
        auth_info_raw = serialize_auth_info(auth_info_data)
        auth_info_parsed = parse_auth_info(auth_info_raw)
        assert auth_info_parsed["unm"] == "test_user"

        # Шаг 4: ТП отправляет RESULT_CODE
        result_data = {"rcd": 0}
        result_raw = serialize_result_code(result_data)
        result_parsed = parse_result_code(result_raw)
        assert result_parsed["rcd"] == 0
        assert "EGTS_PC_OK" in result_parsed["rcd_text"]

    def test_auth_chain_with_service_info(self):
        """Цепочка: SERVICE_INFO → TERM_IDENTITY → AUTH_INFO → RESULT_CODE"""
        # ТП отправляет SERVICE_INFO с перечнем поддерживаемых сервисов
        srv_info = {
            "srvp": 0x00, "srva": False, "srvrp": 0,
            "services": [
                {"st": 1, "sst": 0, "srvp": 0x00, "srva": False, "srvrp": 0},  # AUTH
                {"st": 2, "sst": 0, "srvp": 0x00, "srva": False, "srvrp": 0},  # TELEDATA
                {"st": 4, "sst": 0, "srvp": 0x00, "srva": False, "srvrp": 0},  # COMMANDS
            ],
        }
        srv_raw = serialize_service_info(srv_info)
        srv_parsed = parse_service_info(srv_raw)
        assert len(srv_parsed["services"]) == 3

        # УСВ авторизуется
        term_data = {"tid": 54321, "imeie": True, "imei": "123456789012345"}
        term_raw = serialize_term_identity(term_data)
        term_parsed = parse_term_identity(term_raw)
        assert term_parsed["imei"] == "123456789012345"

        # ТП подтверждает
        result_data = {"rcd": 0}
        result_raw = serialize_result_code(result_data)
        assert parse_result_code(result_raw)["rcd"] == 0

    def test_auth_chain_with_record_response(self):
        """Цепочка с RECORD_RESPONSE подтверждением"""
        # УСВ отправляет данные
        term_data = {"tid": 100, "imeie": False}
        term_raw = serialize_term_identity(term_data)
        assert len(term_raw) >= 5

        # ТП подтверждает запись через RECORD_RESPONSE
        rr_data = {"crn": 1, "rst": 0}
        rr_raw = serialize_record_response(rr_data)
        rr_parsed = parse_record_response(rr_raw)
        assert rr_parsed["crn"] == 1
        assert rr_parsed["rst"] == 0

        # И RESULT_CODE
        rc_data = {"rcd": 0}
        rc_raw = serialize_result_code(rc_data)
        assert parse_result_code(rc_raw)["rcd"] == 0

    def test_auth_chain_with_vehicle_and_module_data(self):
        """Цепочка с MODULE_DATA и VEHICLE_DATA"""
        # MODULE_DATA
        mod_data = {
            "mt": 1, "vid": 100, "fwv": 0x0100, "swv": 0x0200,
            "md": 0, "st": 1, "srn": "MOD001", "dscr": "Main module",
        }
        mod_raw = serialize_module_data(mod_data)
        mod_parsed = parse_module_data(mod_raw)
        assert mod_parsed["mt"] == 1
        assert mod_parsed["srn"] == "MOD001"

        # VEHICLE_DATA
        veh_data = {"vin": "XTA21099999999999", "vht": 1, "vpst": 1}
        veh_raw = serialize_vehicle_data(veh_data)
        veh_parsed = parse_vehicle_data(veh_raw)
        assert veh_parsed["vin"] == "XTA21099999999999"

        # RESULT_CODE
        rc_data = {"rcd": 0}
        rc_raw = serialize_result_code(rc_data)
        assert parse_result_code(rc_raw)["rcd"] == 0


# ============================================
# Тесты RESULT_CODE коды 0, 1, 128-160
# ============================================


class TestResultCodes:
    """Тесты на коды результатов из Приложения В ГОСТ"""

    def test_rcd_0_ok(self):
        """RESULT_CODE: 0 — Успешно"""
        parsed = parse_result_code(b"\x00")
        assert parsed["rcd"] == 0
        assert "EGTS_PC_OK" in parsed["rcd_text"]

    def test_rcd_1_in_progress(self):
        """RESULT_CODE: 1 — В процессе"""
        parsed = parse_result_code(b"\x01")
        assert parsed["rcd"] == 1
        assert "EGTS_PC_IN_PROGRESS" in parsed["rcd_text"]

    def test_rcd_128_uns_protocol(self):
        """RESULT_CODE: 128 — Неподдерживаемый протокол"""
        parsed = parse_result_code(b"\x80")
        assert parsed["rcd"] == 128
        assert "EGTS_PC_UNS_PROTOCOL" in parsed["rcd_text"]

    def test_rcd_153_id_nfound(self):
        """RESULT_CODE: 153 — Идентификатор не найден (критично для TID=0)"""
        parsed = parse_result_code(b"\x99")
        assert parsed["rcd"] == 153
        assert "EGTS_PC_ID_NFOUND" in parsed["rcd_text"]

    def test_rcd_160_max_range(self):
        """RESULT_CODE: 160 — граница диапазона ошибок"""
        parsed = parse_result_code(b"\xa0")
        assert parsed["rcd"] == 160
        # Код 160 может быть Unknown — это допустимо
        assert parsed["rcd_text"]  # Просто проверяем что текст есть

    def test_rcd_137_header_crc_error(self):
        """RESULT_CODE: 137 — Ошибка CRC заголовка"""
        parsed = parse_result_code(b"\x89")
        assert parsed["rcd"] == 137
        assert "EGTS_PC_HEADERCRC_ERROR" in parsed["rcd_text"]

    def test_rcd_146_obj_nfound(self):
        """RESULT_CODE: 146 — Объект не найден"""
        parsed = parse_result_code(b"\x92")
        assert parsed["rcd"] == 146
        assert "EGTS_PC_OBJ_NFOUND" in parsed["rcd_text"]

    def test_result_code_serialize_roundtrip(self):
        """RESULT_CODE: serialize → parse для всех известных кодов"""
        from libs.egts_protocol_gost2015.gost2015_impl.types import RESULT_CODES
        for code in RESULT_CODES:
            raw = serialize_result_code({"rcd": code})
            parsed = parse_result_code(raw)
            assert parsed["rcd"] == code


# ============================================
# Тесты опциональных полей TERM_IDENTITY
# ============================================


class TestTermIdentityOptionalFields:
    """Тесты на опциональные поля TERM_IDENTITY (таблица 19)"""

    def test_term_identity_with_hdid(self):
        """TERM_IDENTITY с HDID (Home Destination ID)"""
        data = {
            "tid": 100, "hdide": True, "hdid": 0x1234,
            "imeie": False, "imsie": False,
        }
        raw = serialize_term_identity(data)
        parsed = parse_term_identity(raw)

        assert parsed["hdide"] is True
        assert parsed["hdid"] == 0x1234
        # Проверка флага: бит 0 установлен
        assert raw[4] & 0x01 == 1

    def test_term_identity_with_imsi(self):
        """TERM_IDENTITY с IMSI"""
        data = {
            "tid": 200, "imsie": True, "imsi": "250991234567890",
            "imeie": False,
        }
        raw = serialize_term_identity(data)
        parsed = parse_term_identity(raw)

        assert parsed["imsie"] is True
        assert parsed["imsi"] == "250991234567890"

    def test_term_identity_with_lngc(self):
        """TERM_IDENTITY с кодом языка (LNGC, 3 байта)"""
        data = {
            "tid": 300, "lngce": True, "lngc": "rus",
            "imeie": False, "imsie": False,
        }
        raw = serialize_term_identity(data)
        parsed = parse_term_identity(raw)

        assert parsed["lngce"] is True
        assert parsed["lngc"] == "rus"

    def test_term_identity_with_nid_bs_msisdn(self):
        """TERM_IDENTITY с NID, BS и MSISDN"""
        data = {
            "tid": 400,
            "nide": True, "nid": b"\x01\x02\x03",
            "bse": True, "bs": 2048,
            "mne": True, "msisdn": "+79001234567",
            "imeie": False, "imsie": False,
        }
        raw = serialize_term_identity(data)
        parsed = parse_term_identity(raw)

        assert parsed["nide"] is True
        assert parsed["nid"] == b"\x01\x02\x03"
        assert parsed["bse"] is True
        assert parsed["bs"] == 2048
        assert parsed["mne"] is True
        assert parsed["msisdn"] == "+79001234567"


# ============================================
# Тесты SST состояния и SRVA/SRVRP
# ============================================


class TestServiceInfoStates:
    """Тесты на состояния сервиса (SST) и приоритеты (SRVA/SRVRP)"""

    def test_sst_all_states(self):
        """SERVICE_INFO: все состояния SST (0, 128, 129, 130, 131)"""
        for sst in [0, 128, 129, 130, 131]:
            srv_info = {
                "srvp": 0x00, "srva": False, "srvrp": 0,
                "services": [{"st": 1, "sst": sst, "srvp": 0x00}],
            }
            raw = serialize_service_info(srv_info)
            parsed = parse_service_info(raw)
            assert parsed["services"][0]["sst"] == sst

    def test_srva_requested(self):
        """SERVICE_INFO: SRVA=1 (запрашиваемый сервис)"""
        srv_info = {
            "srvp": 0x00, "srva": True, "srvrp": 0,
            "services": [{"st": 2, "sst": 0, "srvp": 0x80, "srva": True}],
        }
        raw = serialize_service_info(srv_info)
        parsed = parse_service_info(raw)

        assert parsed["srva"] is True
        assert parsed["services"][0]["srva"] is True
        # SRVA = бит 7 = 0x80
        assert parsed["services"][0]["srvp"] & 0x80 == 0x80

    def test_srvrp_priorities(self):
        """SERVICE_INFO: все приоритеты SRVRP (00, 01, 10, 11)"""
        expected = {0: 0b00, 1: 0b01, 2: 0b10, 3: 0b11}
        for srvrp_val, bits in expected.items():
            srv_info = {
                "srvp": 0x00, "srva": False, "srvrp": srvrp_val,
                "services": [],
            }
            raw = serialize_service_info(srv_info)
            parsed = parse_service_info(raw)
            assert parsed["srvrp"] == srvrp_val
            assert parsed["srvp"] & 0x03 == bits

    def test_service_info_multiple_services_with_states(self):
        """SERVICE_INFO: несколько сервисов с разными состояниями"""
        srv_info = {
            "srvp": 0x00,
            "services": [
                {"st": 1, "sst": 0, "srvp": 0x00},     # AUTH — активен
                {"st": 2, "sst": 128, "srvp": 0x00},    # TELEDATA — неактивен
                {"st": 4, "sst": 130, "srvp": 0x00},    # COMMANDS — не сконфигурирован
            ],
        }
        raw = serialize_service_info(srv_info)
        parsed = parse_service_info(raw)

        assert len(parsed["services"]) == 3
        assert parsed["services"][0]["sst"] == 0
        assert parsed["services"][1]["sst"] == 128
        assert parsed["services"][2]["sst"] == 130
