"""Тест анализа ISSUE-004: RESULT_CODE — APPDATA, не RESPONSE

ВЫВОД: ISSUE-004-A НЕ ПОДТВЕРЖДЕНА в исходной формулировке.
RESULT_CODE отправляется как APPDATA (PT=1), adapter.parse_packet() парсит его корректно.

Реальная проблема: RESULT_CODE от ПЛАТФОРМЫ → УСВ подтверждает RECORD_RESPONSE (PT=0)
"""

import pytest
from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015


# RESULT_CODE — пакет от ПЛАТФОРМЫ к УСВ (пакет #11 из all_packets_correct)
# PT=1 (APPDATA), НЕ RESPONSE!
# PID=32, RN=47, SRT=0x09 (RESULT_CODE), RCD=0 (EGTS_PC_OK)
RESULT_CODE_HEX = "0100000B000B002000012604002F0040010109010000BA4C"
RESULT_CODE_BYTES = bytes.fromhex(RESULT_CODE_HEX)

# RECORD_RESPONSE от УСВ — подтверждение RESULT_CODE (пакет #12 из all_packets_correct)
# PT=0 (RESPONSE), PID=44, RPID=32, PR=0
# RN=75, CRN=47, RST=0
RECORD_RESPONSE_HEX = "0100000B0010002C00006A20000006004B008001010003002F0000F139"
RECORD_RESPONSE_BYTES = bytes.fromhex(RECORD_RESPONSE_HEX)


class TestResultCodeIsAppData:
    """RESULT_CODE — это APPDATA (PT=1), не RESPONSE (PT=0)"""

    @pytest.fixture
    def adapter(self):
        return EgtsProtocol2015()

    def test_result_code_pt_is_appdata(self, adapter: EgtsProtocol2015):
        """RESULT_CODE имеет PT=1 (APPDATA), не PT=0 (RESPONSE)"""
        result = adapter.parse_packet(RESULT_CODE_BYTES)
        assert result.packet is not None
        assert result.packet.packet_type == 1, "PT=1 — APPDATA, не RESPONSE"

    def test_result_code_has_records(self, adapter: EgtsProtocol2015):
        """RESULT_CODE содержит записи — adapter.parse_packet() парсит их"""
        result = adapter.parse_packet(RESULT_CODE_BYTES)
        assert result.packet is not None
        assert len(result.packet.records) == 1, "RESULT_CODE содержит 1 запись"

    def test_result_code_record_rn(self, adapter: EgtsProtocol2015):
        """RN записи RESULT_CODE = 47"""
        result = adapter.parse_packet(RESULT_CODE_BYTES)
        assert result.packet is not None and result.packet.records
        assert result.packet.records[0].record_id == 47, "RN=47"

    def test_result_code_subrecord_type(self, adapter: EgtsProtocol2015):
        """Subrecord RESULT_CODE распознан"""
        result = adapter.parse_packet(RESULT_CODE_BYTES)
        assert result.packet is not None and result.packet.records
        subs = result.packet.records[0].subrecords
        assert len(subs) == 1
        assert subs[0].subrecord_type == "EGTS_SR_RESULT_CODE", (
            f"Ожидался RESULT_CODE, получен: {subs[0].subrecord_type}"
        )

    def test_result_code_pid(self, adapter: EgtsProtocol2015):
        """PID RESULT_CODE = 32"""
        result = adapter.parse_packet(RESULT_CODE_BYTES)
        assert result.packet is not None
        assert result.packet.packet_id == 32, "PID=32"

    def test_result_code_extra(self, adapter: EgtsProtocol2015):
        """extra заполнен для RESULT_CODE"""
        result = adapter.parse_packet(RESULT_CODE_BYTES)
        assert result.extra.get("service") == 1, "service=1 (AUTH)"
        assert result.extra.get("subrecord_type") == "EGTS_SR_RESULT_CODE"


class TestRecordResponseIsResponse:
    """RECORD_RESPONSE от УСВ — подтверждение RESULT_CODE"""

    @pytest.fixture
    def adapter(self):
        return EgtsProtocol2015()

    def test_record_response_pt_is_response(self, adapter: EgtsProtocol2015):
        """RECORD_RESPONSE имеет PT=0 (RESPONSE)"""
        result = adapter.parse_packet(RECORD_RESPONSE_BYTES)
        assert result.packet is not None
        assert result.packet.packet_type == 0, "PT=0 — RESPONSE"

    def test_record_response_rpid(self, adapter: EgtsProtocol2015):
        """RPID = 32 (подтверждает RESULT_CODE PID=32)"""
        result = adapter.parse_packet(RECORD_RESPONSE_BYTES)
        assert result.packet is not None
        assert result.packet.response_packet_id == 32, "RPID=32"

    def test_record_response_pr(self, adapter: EgtsProtocol2015):
        """PR = 0 (EGTS_PC_OK)"""
        result = adapter.parse_packet(RECORD_RESPONSE_BYTES)
        assert result.packet is not None
        assert result.packet.processing_result == 0, "PR=0"

    def test_record_response_has_records(self, adapter: EgtsProtocol2015):
        """RECORD_RESPONSE содержит запись с CRN"""
        result = adapter.parse_packet(RECORD_RESPONSE_BYTES)
        assert result.packet is not None
        assert len(result.packet.records) == 1, "1 запись"
        assert result.packet.records[0].record_id == 75, "RN=75"

    def test_record_response_crn(self, adapter: EgtsProtocol2015):
        """CRN = 47 (подтверждает RN=47 из RESULT_CODE)"""
        result = adapter.parse_packet(RECORD_RESPONSE_BYTES)
        assert result.extra.get("confirmed_record_number") == 47, "CRN=47"
        assert result.extra.get("record_status") == 0, "RST=0"


class TestIssue004A_Conclusion:
    """Вывод по ISSUE-004-A"""

    @pytest.fixture
    def adapter(self):
        return EgtsProtocol2015()

    def test_issue004a_not_confirmed_result_code_parsed_correctly(self, adapter: EgtsProtocol2015):
        """ISSUE-004-A НЕ ПОДТВЕРЖДЕНА: adapter.parse_packet() корректно парсит RESULT_CODE

        RESULT_CODE — это APPDATA (PT=1), adapter парсит записи, extra заполнен.
        Проблема НЕ в парсинге adapter.
        """
        result = adapter.parse_packet(RESULT_CODE_BYTES)

        # Всё работает:
        assert result.errors == []
        assert result.packet is not None
        assert result.packet.packet_type == 1  # APPDATA
        assert len(result.packet.records) == 1
        assert result.packet.records[0].record_id == 47
        assert result.packet.records[0].subrecords[0].subrecord_type == "EGTS_SR_RESULT_CODE"
        assert result.extra.get("service") == 1
        assert result.extra.get("subrecord_type") == "EGTS_SR_RESULT_CODE"
