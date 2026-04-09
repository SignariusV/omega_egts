"""
Тесты для FIRMWARE сервиса EGTS (ГОСТ 33465-2015, раздел 6.7.4)

mypy: ignore-errors — тесты не типизируются (соглашение проекта).
"""

# mypy: ignore-errors
import pytest

from libs.egts_protocol_gost2015.gost2015_impl.services.firmware import (
    assemble_parts,
    calculate_crc16_ccitt,
    create_config_update,
    create_firmware_update,
    create_odh,
    parse_odh,
    parse_service_full_data,
    parse_service_part_data,
    serialize_service_full_data,
    serialize_service_part_data,
    split_firmware_to_parts,
    validate_firmware_data,
    verify_firmware_signature,
)


class TestCrc16Ccitt:
    """Тесты для CRC16-CCITT"""

    def test_calculate_crc16_basic(self):
        """Базовый расчет CRC16"""
        data = b"123456789"
        crc = calculate_crc16_ccitt(data)
        assert crc == 0x29B1

    def test_calculate_crc16_empty(self):
        """CRC16 для пустых данных"""
        crc = calculate_crc16_ccitt(b"")
        assert crc == 0xFFFF

    def test_verify_signature_valid(self):
        """Проверка валидной сигнатуры"""
        data = b"test data"
        crc = calculate_crc16_ccitt(data)
        assert verify_firmware_signature(data, crc) is True

    def test_verify_signature_invalid(self):
        """Проверка невалидной сигнатуры"""
        data = b"test data"
        crc = calculate_crc16_ccitt(data)
        assert verify_firmware_signature(data, crc + 1) is False


class TestObjectDataHeader:
    """Тесты для ODH заголовка"""

    def test_create_odh_basic(self):
        """Создание базового ODH"""
        odh = create_odh(
            object_attribute=0x00, object_type=0x00, module_type=0x01,
            component_id=1, version=(2, 34), whole_signature=0x1234,
        )
        assert len(odh) == 8  # OA(1) + OT+MT(1) + CMI(1) + VER(2) + WOS(2) + D(1)
        assert odh[0] == 0x00  # OA
        assert odh[1] == 0x01  # OT=0, MT=1
        assert odh[2] == 0x01  # CMI

    def test_create_odh_with_filename(self):
        """ODH с именем файла"""
        odh = create_odh(
            object_attribute=0x02, object_type=0x01, module_type=0x00,
            component_id=5, version=(1, 0), whole_signature=0xABCD,
            file_name="config.json",
        )
        # OA(1) + OT+MT(1) + CMI(1) + VER(2) + WOS(2) + FN(11) + D(1) = 19
        assert len(odh) == 19
        assert odh[0] == 0x02
        assert odh[-1] == 0x00  # Разделитель
        assert b"config.json" in odh

    def test_create_odh_filename_too_long(self):
        """ODH: имя файла > 63 байт"""
        with pytest.raises(ValueError, match="Имя файла слишком длинное"):
            create_odh(
                object_attribute=0, object_type=0, module_type=1,
                component_id=1, version=(1, 0), whole_signature=0,
                file_name="a" * 64,
            )

    def test_parse_odh_basic(self):
        """Парсинг базового ODH"""
        odh = create_odh(
            object_attribute=0, object_type=0, module_type=1,
            component_id=2, version=(3, 45), whole_signature=0x5678,
        )
        result = parse_odh(odh)

        assert result["oa"] == 0
        assert result["ot"] == 0
        assert result["mt"] == 1
        assert result["cmi"] == 2
        assert result["version"] == (3, 45)
        assert result["whole_signature"] == 0x5678
        assert result["file_name"] == ""


class TestServiceFullData:
    """Тесты для SERVICE_FULLUBDATA"""

    def test_serialize_service_full_data(self):
        """Сборка SERVICE_FULL_DATA"""
        odh = create_odh(
            object_attribute=0, object_type=0, module_type=1,
            component_id=1, version=(1, 0), whole_signature=0x1234,
        )
        object_data = b"\x00\x01\x02\x03"

        raw = serialize_service_full_data(odh, object_data)
        assert raw[:len(odh)] == odh
        assert raw[len(odh):] == object_data

    def test_parse_service_full_data(self):
        """Парсинг SERVICE_FULL_DATA"""
        odh = create_odh(
            object_attribute=0, object_type=0, module_type=1,
            component_id=1, version=(2, 0), whole_signature=0xABCD,
            file_name="fw.bin",
        )
        object_data = b"\xDE\xAD\xBE\xEF"
        raw = serialize_service_full_data(odh, object_data)

        result = parse_service_full_data(raw)
        assert result["odh"] == odh
        assert result["od"] == object_data
        assert result["odh_parsed"]["file_name"] == "fw.bin"


class TestServicePartData:
    """Тесты для SERVICE_PART_DATA"""

    def test_serialize_service_part_data_first(self):
        """Сборка SERVICE_PART_DATA (первая часть с ODH)"""
        odh = create_odh(
            object_attribute=0, object_type=0, module_type=1,
            component_id=1, version=(1, 0), whole_signature=0x1234,
        )
        od = b"\x00\x01\x02\x03"

        raw = serialize_service_part_data(
            entity_id=1, part_number=1, total_parts=3,
            odh=odh, object_data=od,
        )

        result = parse_service_part_data(raw)
        assert result["id"] == 1
        assert result["pn"] == 1
        assert result["epq"] == 3
        assert result["odh"] == odh
        assert result["od"] == od
        assert result["is_first_part"] is True

    def test_serialize_service_part_data_other(self):
        """Сборка SERVICE_PART_DATA (не первая часть без ODH)"""
        od = b"\xAA\xBB\xCC"

        raw = serialize_service_part_data(
            entity_id=1, part_number=2, total_parts=3,
            object_data=od,
        )

        result = parse_service_part_data(raw)
        assert result["pn"] == 2
        assert result["odh"] is None
        assert result["od"] == od
        assert result["is_first_part"] is False

    def test_parse_service_part_data_minimal_non_first(self):
        """Парсинг минимальной не-первой части (7 байт)"""
        # ID(2) + PN(2) + EPQ(2) + OD(1) = 7
        raw = b"\x01\x00\x02\x00\x03\x00\xFF"
        result = parse_service_part_data(raw)

        assert result["id"] == 1
        assert result["pn"] == 2
        assert result["epq"] == 3
        assert result["od"] == b"\xFF"
        assert result["is_first_part"] is False

    def test_parse_service_part_data_pn_exceeds_epq(self):
        """SERVICE_PART_DATA: PN > EPQ"""
        raw = b"\x01\x00\x04\x00\x03\x00" + b"\x00" * 8  # PN=4, EPQ=3
        with pytest.raises(ValueError, match="Номер части.*больше"):
            parse_service_part_data(raw)


class TestSplitAndAssemble:
    """Тесты для split_firmware_to_parts и assemble_parts"""

    def test_split_and_assemble_basic(self):
        """Разбиение и сборка прошивки"""
        firmware = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09" * 10  # 100 байт

        parts_meta = split_firmware_to_parts(
            firmware, version=(1, 0), component_id=1, max_part_size=64,
        )
        parts = [p[0] for p in parts_meta]  # Первые элементы — bytes
        assert len(parts) >= 2

        # Собираем OD из частей
        od_list = []
        for part in parts:
            parsed = parse_service_part_data(part)
            od_list.append(parsed["od"])

        assembled, metadata = assemble_parts(od_list)
        assert assembled == firmware
        assert metadata["size"] == len(firmware)

    def test_split_single_part(self):
        """Прошивка помещается в одну часть"""
        firmware = b"\xAA\xBB\xCC"
        parts_meta = split_firmware_to_parts(
            firmware, version=(1, 0), component_id=1, max_part_size=256,
        )
        parts = [p[0] for p in parts_meta]

        assert len(parts) == 1
        parsed = parse_service_part_data(parts[0])
        assert parsed["pn"] == 1
        assert parsed["epq"] == 1
        assert parsed["od"] == firmware

    def test_assemble_with_crc_check(self):
        """Сборка с проверкой CRC"""
        firmware = b"\x01\x02\x03\x04\x05"
        expected_crc = calculate_crc16_ccitt(firmware)

        _assembled, metadata = assemble_parts([firmware], expected_crc=expected_crc)
        assert metadata["crc_valid"] is True
        assert metadata["calculated_crc"] == expected_crc

    def test_assemble_crc_mismatch(self):
        """Сборка с несовпадающим CRC"""
        firmware = b"\x01\x02\x03"
        with pytest.raises(ValueError, match="CRC16 не совпадает"):
            assemble_parts([firmware], expected_crc=0xFFFF)

    def test_split_empty_firmware(self):
        """split_firmware_to_parts: пустая прошивка → ValueError"""
        with pytest.raises(ValueError, match="Пустые данные прошивки"):
            split_firmware_to_parts(
                b"", version=(1, 0), component_id=1, max_part_size=64,
            )


class TestCreateFirmwareUpdate:
    """Тесты для create_firmware_update"""

    def test_create_firmware_update(self):
        """Создание обновления прошивки"""
        firmware = b"\x00\x01\x02\x03"
        subrecord_data, metadata = create_firmware_update(
            firmware, component_id=1, version=(2, 0),
        )

        assert isinstance(subrecord_data, bytes)
        assert metadata["version"] == (2, 0)
        assert metadata["size"] == 4

    def test_create_config_update(self):
        """Создание обновления конфигурации"""
        config = b'{"key": "value"}'
        subrecord_data, metadata = create_config_update(
            config, component_id=5, version=(1, 2),
        )

        assert isinstance(subrecord_data, bytes)
        assert metadata["version"] == (1, 2)
        assert metadata["size"] == len(config)


class TestValidateFirmwareData:
    """Тесты для validate_firmware_data"""

    def test_validate_valid_data(self):
        """Валидация корректных данных"""
        assert validate_firmware_data(b"\x00\x01\x02\x03") is True

    def test_validate_empty_data(self):
        """Валидация пустых данных"""
        assert validate_firmware_data(b"") is False


# ============================================
# Тесты граничных значений PN/EPQ/ID
# ============================================


class TestFirmwareBoundary:
    """Тесты на граничные значения ID, PN, EPQ"""

    def test_part_data_pn_1_epq_65535(self):
        """SERVICE_PART_DATA: PN=1, EPQ=65535 (границы)"""
        od = b"\x01\x02\x03"
        odh = create_odh(version=(1, 0), whole_signature=0, file_name=None)
        raw = serialize_service_part_data(
            entity_id=1, part_number=1, total_parts=65535,
            object_data=od, odh=odh,
        )
        parsed = parse_service_part_data(raw)

        assert parsed["pn"] == 1
        assert parsed["epq"] == 65535
        assert parsed["id"] == 1

    def test_part_data_id_65535(self):
        """SERVICE_PART_DATA: ID=65535 (максимум)"""
        od = b"\x01"
        odh = create_odh(version=(1, 0), whole_signature=0, file_name=None)
        raw = serialize_service_part_data(
            entity_id=65535, part_number=1, total_parts=1,
            object_data=od, odh=odh,
        )
        parsed = parse_service_part_data(raw)

        assert parsed["id"] == 65535

    def test_part_data_pn_exceeds_epq(self):
        """SERVICE_PART_DATA: PN > EPQ — serialize отклоняет"""
        with pytest.raises(ValueError, match="Номер части не может быть больше"):
            serialize_service_part_data(
                entity_id=1, part_number=5, total_parts=3,
                object_data=b"\x01", odh=None,
            )

    def test_odh_version_max(self):
        """ODH: версия (255, 255)"""
        odh_bytes = create_odh(version=(255, 255), whole_signature=0, file_name=None)
        parsed = parse_odh(odh_bytes)
        assert parsed["version"] == (255, 255)


# ============================================
# Интеграционный roundtrip FULL_DATA
# ============================================


class TestFirmwareFullDataRoundtrip:
    """Интеграционные тесты FULL_DATA roundtrip"""

    def test_create_firmware_update_parse_verify(self):
        """create_firmware_update → parse_service_full_data → verify"""
        firmware = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        subrecord_data, _metadata = create_firmware_update(
            firmware, component_id=1, version=(2, 1),
            file_name="test.bin",
        )

        # Парсим SERVICE_FULL_DATA
        parsed = parse_service_full_data(subrecord_data)

        assert parsed["od"] == firmware
        assert parsed["odh_parsed"]["version"] == (2, 1)

    def test_create_config_update_parse_verify(self):
        """create_config_update → parse_service_full_data → verify"""
        config = b'{"server": "example.com", "port": 8080}'
        subrecord_data, _metadata = create_config_update(
            config, component_id=3, version=(1, 0),
        )

        parsed = parse_service_full_data(subrecord_data)

        assert parsed["od"] == config
