"""Тесты для системы строковых алиасов сценариев."""

import pytest

from core.scenario_aliases import resolve_alias, resolve_aliases_recursive


class TestResolveAlias:
    """Тесты функции resolve_alias."""

    def test_packet_type_alias(self):
        assert resolve_alias("packet_type", "APPDATA") == 1
        assert resolve_alias("packet_type", "RESPONSE") == 0

    def test_service_type_alias(self):
        assert resolve_alias("service_type", "COMMANDS") == 4
        assert resolve_alias("service_type", "AUTH") == 1

    def test_subrecord_type_alias(self):
        assert resolve_alias("subrecord_type", "COMMAND_DATA") == 51
        assert resolve_alias("subrecord_type", "TERM_IDENTITY") == 1

    def test_ct_alias(self):
        assert resolve_alias("ct", "COM") == 5
        assert resolve_alias("ct", "COMCONF") == 1

    def test_cct_alias(self):
        assert resolve_alias("cct", "OK") == 0
        assert resolve_alias("cct", "ERROR") == 1

    def test_act_alias(self):
        assert resolve_alias("act", "SET") == 2
        assert resolve_alias("act", "QUERY") == 1

    def test_ccd_alias(self):
        assert resolve_alias("ccd", "EGTS_GPRS_APN") == 257
        assert resolve_alias("ccd", "EGTS_SERVER_ADDRESS") == 258
        assert resolve_alias("ccd", "EGTS_SET_SERVER_ADDRESS_V2") == 1026
        assert resolve_alias("ccd", "EGTS_UNIT_ID") == 1028

    def test_chs_alias(self):
        assert resolve_alias("chs", "CP1251") == 0
        assert resolve_alias("chs", "ASCII") == 1

    def test_rcd_alias(self):
        assert resolve_alias("rcd", "OK") == 0
        assert resolve_alias("rcd", "IN_PROGRESS") == 1

    def test_numeric_value_unchanged(self):
        """Числовые значения не должны изменяться."""
        assert resolve_alias("ct", 5) == 5
        assert resolve_alias("ccd", 1026) == 1026

    def test_unknown_field_unchanged(self):
        """Неизвестные поля не должны изменяться."""
        assert resolve_alias("unknown_field", "some_value") == "some_value"

    def test_unknown_alias_unchanged(self):
        """Неизвестные алиасы возвращают исходное значение."""
        assert resolve_alias("ct", "UNKNOWN_TYPE") == "UNKNOWN_TYPE"


class TestResolveAliasesRecursive:
    """Тесты рекурсивного резолвера алиасов."""

    def test_simple_dict(self):
        data = {
            "packet_type": "APPDATA",
            "service_type": "COMMANDS",
        }
        result = resolve_aliases_recursive(data)
        assert result["packet_type"] == 1
        assert result["service_type"] == 4

    def test_nested_dict(self):
        data = {
            "packet": {
                "packet_type": "APPDATA",
                "records": [
                    {
                        "service_type": "COMMANDS",
                        "subrecords": [
                            {
                                "subrecord_type": "COMMAND_DATA",
                                "data": {
                                    "ct": "COM",
                                    "cct": "OK",
                                    "cd": {
                                        "act": "SET",
                                        "ccd": "EGTS_GPRS_APN",
                                    },
                                },
                            }
                        ],
                    }
                ],
            }
        }
        result = resolve_aliases_recursive(data)
        packet = result["packet"]
        assert packet["packet_type"] == 1
        record = packet["records"][0]
        assert record["service_type"] == 4
        sr = record["subrecords"][0]
        assert sr["subrecord_type"] == 51
        cd = sr["data"]["cd"]
        assert cd["act"] == 2
        assert cd["ccd"] == 257

    def test_list_processing(self):
        data = {
            "records": [
                {"service_type": "AUTH"},
                {"service_type": "COMMANDS"},
            ]
        }
        result = resolve_aliases_recursive(data)
        assert result["records"][0]["service_type"] == 1
        assert result["records"][1]["service_type"] == 4

    def test_mixed_numeric_and_string(self):
        """Смешанные числовые и строковые значения."""
        data = {
            "packet_type": "APPDATA",
            "packet_id": 27,  # число
            "service_type": "COMMANDS",
            "record_id": 42,  # число
        }
        result = resolve_aliases_recursive(data)
        assert result["packet_type"] == 1
        assert result["packet_id"] == 27
        assert result["service_type"] == 4
        assert result["record_id"] == 42

    def test_deep_nesting(self):
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "ct": "COM",
                        "ccd": "EGTS_UNIT_ID",
                    }
                }
            }
        }
        result = resolve_aliases_recursive(data)
        inner = result["level1"]["level2"]["level3"]
        assert inner["ct"] == 5
        assert inner["ccd"] == 1028

    def test_preserves_non_alias_strings(self):
        """Строки, не являющиеся алиасами, сохраняются."""
        data = {
            "dt": "internet",
            "name": "test_scenario",
            "ccd": "EGTS_GPRS_APN",
        }
        result = resolve_aliases_recursive(data)
        assert result["dt"] == "internet"
        assert result["name"] == "test_scenario"
        assert result["ccd"] == 257

    def test_empty_structures(self):
        assert resolve_aliases_recursive({}) == {}
        assert resolve_aliases_recursive([]) == []
