"""Тесты динамической генерации пакетов в SendStep."""

import pytest
from core.scenario import SendStep, ScenarioContext
from libs.egts.models import Packet, Record, Subrecord


class TestDictToPacketConversion:
    """Тесты конвертации dict -> Packet."""

    def test_simple_response_packet(self):
        """Конвертация простого RESPONSE-пакета."""
        step = SendStep(name="test")

        packet_dict = {
            "packet_id": 10,
            "packet_type": 0,
            "response_packet_id": 5,
            "processing_result": 0,
            "records": [
                {
                    "record_id": 5,
                    "service_type": 1,
                    "rsod": True,
                    "subrecords": [
                        {
                            "subrecord_type": 0,
                            "data": {"crn": 5, "rst": 0}
                        }
                    ]
                }
            ]
        }

        packet = step._dict_to_packet(packet_dict)

        assert packet.packet_id == 10
        assert packet.packet_type == 0
        assert packet.response_packet_id == 5
        assert len(packet.records) == 1
        assert packet.records[0].record_id == 5
        assert packet.records[0].service_type == 1

    def test_hex_to_binary_conversion(self):
        """Конвертация hex-строк в binary."""
        step = SendStep(name="test")

        packet_dict = {
            "packet_id": 22,
            "packet_type": 1,
            "records": [
                {
                    "record_id": 37,
                    "service_type": 4,
                    "subrecords": [
                        {
                            "subrecord_type": 51,
                            "data": {
                                "cd_hex": "0000011401"
                            }
                        }
                    ]
                }
            ]
        }

        packet = step._dict_to_packet(packet_dict)

        assert packet.records[0].subrecords[0].data["cd"] == b'\x00\x00\x01\x14\x01'
        assert "cd_hex" not in packet.records[0].subrecords[0].data

    def test_nested_hex_conversion(self):
        """Конвертация hex в nested структурах."""
        step = SendStep(name="test")

        packet_dict = {
            "packet_id": 1,
            "packet_type": 1,
            "records": [
                {
                    "record_id": 1,
                    "service_type": 1,
                    "subrecords": [
                        {
                            "subrecord_type": 1,
                            "data": {
                                "nested": {
                                    "value_hex": "ABCD"
                                }
                            }
                        }
                    ]
                }
            ]
        }

        packet = step._dict_to_packet(packet_dict)

        assert packet.records[0].subrecords[0].data["nested"]["value"] == b'\xAB\xCD'

    def test_missing_required_fields(self):
        """Ошибка при отсутствии обязательных полей."""
        step = SendStep(name="test")

        with pytest.raises(ValueError, match="packet_id is required"):
            step._dict_to_packet({"packet_type": 1})

        with pytest.raises(ValueError, match="packet_type is required"):
            step._dict_to_packet({"packet_id": 1})


class TestBuildFromTemplateBytes:
    """Тесты сборки пакета из шаблона."""

    def test_old_format_packet_bytes(self):
        """Старый формат с packet_bytes — обратная совместимость."""
        step = SendStep(
            name="test",
            build={"packet_bytes": b"\x01\x02\x03", "pid": 1},
        )
        ctx = ScenarioContext()

        result = step._build_from_template_bytes(ctx)

        assert result == b"\x01\x02\x03"

    def test_new_format_packet(self):
        """Новый формат с packet — динамическая генерация."""
        step = SendStep(
            name="test",
            build={
                "packet": {
                    "packet_id": 10,
                    "packet_type": 0,
                    "records": []
                }
            },
        )
        ctx = ScenarioContext()

        result = step._build_from_template_bytes(ctx)

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_missing_packet_key(self):
        """Ошибка при отсутствии packet в новом формате."""
        step = SendStep(
            name="test",
            build={"other_key": "value"},
        )
        ctx = ScenarioContext()

        with pytest.raises(ValueError, match="'packet' key is required"):
            step._build_from_template_bytes(ctx)


class TestVariableSubstitution:
    """Тесты подстановки переменных."""

    def test_simple_variable_substitution(self):
        """Подстановка простых переменных."""
        ctx = ScenarioContext()
        ctx.set("tid", 12345)
        ctx.set("imei", "123456789012345")

        step = SendStep(name="test")
        step.build = {
            "packet": {
                "packet_id": "{{tid}}",
                "packet_type": 1,
                "records": [
                    {
                        "record_id": 1,
                        "service_type": 1,
                        "subrecords": [
                            {
                                "subrecord_type": 1,
                                "data": {
                                    "TID": "{{tid}}",
                                    "IMEI": "{{imei}}"
                                }
                            }
                        ]
                    }
                ]
            }
        }

        result = step._build_from_template_bytes(ctx)

        assert isinstance(result, bytes)

    def test_special_variables(self):
        """Подстановка специальных переменных next_pid, next_rn."""
        ctx = ScenarioContext()
        ctx.set("next_pid", 100)
        ctx.set("next_rn", 200)

        step = SendStep(name="test")
        step.build = {
            "packet": {
                "packet_id": "{{next_pid}}",
                "packet_type": 0,
                "records": [
                    {
                        "record_id": "{{next_rn}}",
                        "service_type": 1,
                        "subrecords": []
                    }
                ]
            }
        }

        result = step._build_from_template_bytes(ctx)

        assert isinstance(result, bytes)