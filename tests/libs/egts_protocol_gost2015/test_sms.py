"""Тесты на SMS PDU модуль (ГОСТ 33465-2015, раздел 5.7)

# mypy: disable-error-code="no-untyped-call"

Покрывает:
- create_sms_pdu — создание SMS PDU
- parse_sms_pdu — парсинг SMS PDU
- split_for_sms_concatenation — разбиение на части
- create_concatenated_sms_list — конкатенированные SMS
- SMSReassembler — сборка фрагментов
- EgtsProtocol2015.build_sms_pdu / parse_sms_pdu — адаптер
"""

import pytest

from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015
from libs.egts_protocol_gost2015.gost2015_impl.sms import (
    SMSDataCodingScheme,
    SMSNumberingPlan,
    SMSReassembler,
    SMSTypeOfNumber,
    create_concatenated_sms_list,
    create_sms_pdu,
    parse_sms_pdu,
    split_for_sms_concatenation,
)


class TestSMSEncoding:
    """Тесты на кодирование/декодирование телефонных номеров"""

    def test_type_of_number_values(self) -> None:
        """TON значения корректны"""
        assert SMSTypeOfNumber.UNKNOWN == 0b000
        assert SMSTypeOfNumber.INTERNATIONAL == 0b001
        assert SMSTypeOfNumber.NATIONAL == 0b010
        assert SMSTypeOfNumber.ALPHANUMERIC == 0b101

    def test_numbering_plan_values(self) -> None:
        """NPI значения корректны"""
        assert SMSNumberingPlan.UNKNOWN == 0b0000
        assert SMSNumberingPlan.ISDN_TELEPHONY == 0b0001
        assert SMSNumberingPlan.DATA == 0b0011

    def test_data_coding_scheme(self) -> None:
        """8-битная кодировка"""
        assert SMSDataCodingScheme.BINARY_8BIT == 0x04


class TestCreateSmsPdu:
    """Тесты на создание SMS PDU"""

    def test_minimal_pdu_no_smsc(self) -> None:
        """Минимальный PDU без SMSC"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\x01\x02\x03",
        )
        assert pdu[0] == 0x00  # SMSC из SIM
        assert pdu[1] == 0x01  # TP-MTI = SMS-SUBMIT

    def test_pdu_with_smsc(self) -> None:
        """PDU с номером SMSC"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\xAA",
            smsc_number="+79009000900",
        )
        assert pdu[0] > 0  # SMSC длина > 0
        # TP-MTI находится после SMSC: SMSC_len(1) + SMSC_data(pdu[0]) + TP-MTI
        tp_mti_offset = pdu[0] + 1
        assert pdu[tp_mti_offset] == 0x01  # TP-MTI

    def test_pdu_with_status_report(self) -> None:
        """PDU с запросом отчёта о доставке"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\x00",
            request_status_report=True,
        )
        # TP_SRR = бит 2 = 0x04
        assert pdu[1] & 0x04 == 0x04

    def test_pdu_message_reference(self) -> None:
        """TP-MR сохраняется"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\x00",
            message_reference=42,
        )
        # TP-MR находится после TP-Flags
        # Находим позицию: SMSC(1) + TP-Flags(1) = offset 2
        if pdu[0] == 0:  # без SMSC
            assert pdu[2] == 42
        else:  # со SMSC
            assert pdu[pdu[0] + 2] == 42

    def test_pdu_user_data_preserved(self) -> None:
        """Пользовательские данные сохраняются в PDU"""
        user_data = b"\xDE\xAD\xBE\xEF"
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=user_data,
        )
        assert user_data in pdu


class TestParseSmsPdu:
    """Тесты на парсинг SMS PDU"""

    def test_too_short_pdu_raises(self) -> None:
        """Слишком короткий PDU вызывает ValueError"""
        with pytest.raises(ValueError, match="Слишком короткие данные"):
            parse_sms_pdu(b"\x00\x01\x02")

    def test_parse_minimal_pdu(self) -> None:
        """Парсинг минимального PDU"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\x01\x02\x03",
        )
        result = parse_sms_pdu(pdu)

        assert result["sender"] == "+79001234567"
        assert result["user_data"] == b"\x01\x02\x03"
        assert result["concatenated"] is False
        assert result["concat_info"] is None

    def test_parse_pdu_with_smsc(self) -> None:
        """Парсинг PDU с SMSC"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\xAA",
            smsc_number="+79009000900",
        )
        result = parse_sms_pdu(pdu)

        assert result["smsc"] == "+79009000900"
        assert result["user_data"] == b"\xAA"

    def test_parse_status_report_flag(self) -> None:
        """Флаг запроса отчёта сохраняется"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\x00",
            request_status_report=True,
        )
        result = parse_sms_pdu(pdu)

        assert result["status_report_requested"] is True

    def test_parse_message_reference(self) -> None:
        """TP-MR восстанавливается"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\x00",
            message_reference=99,
        )
        result = parse_sms_pdu(pdu)

        assert result["message_reference"] == 99


class TestSmsRoundtrip:
    """Тесты roundtrip: create → parse"""

    def test_roundtrip_preserves_user_data(self) -> None:
        """Пользовательские данные сохраняются после roundtrip"""
        original = b"\xDE\xAD\xBE\xEF\x01\x02\x03\x04"
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=original,
        )
        result = parse_sms_pdu(pdu)

        assert result["user_data"] == original

    def test_roundtrip_preserves_sender(self) -> None:
        """Номер отправителя сохраняется после roundtrip"""
        pdu = create_sms_pdu(
            phone_number="+79009998877",
            user_data=b"\x00",
        )
        result = parse_sms_pdu(pdu)

        assert result["sender"] == "+79009998877"

    def test_roundtrip_preserves_smsc(self) -> None:
        """Номер SMSC сохраняется после roundtrip"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\x00",
            smsc_number="+79009000900",
        )
        result = parse_sms_pdu(pdu)

        assert result["smsc"] == "+79009000900"


class TestConcatenation:
    """Тесты на конкатенацию SMS"""

    def test_concatenated_pdu_has_udhi_flag(self) -> None:
        """Конкатенированный PDU имеет TP_UDHI"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\x00",
            concatenated=True,
            concat_ref=1,
            concat_total=3,
            concat_seq=1,
        )
        # TP_UDHI = бит 6
        assert pdu[1] & 0x40 == 0x40

    def test_parse_concatenated_pdu(self) -> None:
        """Парсинг конкатенированного PDU"""
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=b"\xAB\xCD",
            concatenated=True,
            concat_ref=42,
            concat_total=5,
            concat_seq=3,
        )
        result = parse_sms_pdu(pdu)

        assert result["concatenated"] is True
        assert result["concat_info"] is not None
        assert result["concat_info"]["reference"] == 42
        assert result["concat_info"]["total"] == 5
        assert result["concat_info"]["sequence"] == 3
        assert result["user_data"] == b"\xAB\xCD"

    def test_split_for_sms_concatenation(self) -> None:
        """Разбиение данных на части"""
        data = b"\x00" * 300  # 300 байт > 134
        parts = split_for_sms_concatenation(data, max_part_size=134)

        assert len(parts) == 3  # 300 / 134 = 3 части
        assert parts[0][1] == 3  # total = 3
        assert parts[0][2] == 1  # seq = 1
        assert len(parts[0][3]) == 134
        assert len(parts[1][3]) == 134
        assert len(parts[2][3]) == 32  # остаток

    def test_split_empty_data(self) -> None:
        """Пустые данные — пустой список"""
        assert split_for_sms_concatenation(b"") == []

    def test_create_concatenated_sms_list(self) -> None:
        """Создание списка конкатенированных SMS"""
        data = b"\x00" * 300
        sms_list = create_concatenated_sms_list(
            phone_number="+79001234567",
            egts_packet=data,
        )

        assert len(sms_list) == 3
        # Все PDU валидны
        for pdu in sms_list:
            result = parse_sms_pdu(pdu)
            assert result["concatenated"] is True


class TestSMSReassembler:
    """Тесты на сборку конкатенированных SMS"""

    def test_reassemble_complete_message(self) -> None:
        """Полная сборка сообщения из фрагментов"""
        reassembler = SMSReassembler()

        # Добавляем фрагменты в произвольном порядке
        reassembler.add_fragment(ref=1, total=3, seq=2, data=b"\x02\x02")
        reassembler.add_fragment(ref=1, total=3, seq=3, data=b"\x03\x03")
        reassembler.add_fragment(ref=1, total=3, seq=1, data=b"\x01\x01")

        result = reassembler.get_complete_message(1)
        assert result == b"\x01\x01\x02\x02\x03\x03"

    def test_reassemble_incomplete_message(self) -> None:
        """Неполное сообщение возвращает None"""
        reassembler = SMSReassembler()

        reassembler.add_fragment(ref=1, total=3, seq=1, data=b"\x01")
        reassembler.add_fragment(ref=1, total=3, seq=2, data=b"\x02")
        # seq=3 отсутствует

        assert reassembler.get_complete_message(1) is None

    def test_reassemble_unknown_ref(self) -> None:
        """Неизвестный reference возвращает None"""
        reassembler = SMSReassembler()
        assert reassembler.get_complete_message(99) is None

    def test_reassemble_clear(self) -> None:
        """Очистка фрагментов"""
        reassembler = SMSReassembler()
        reassembler.add_fragment(ref=1, total=1, seq=1, data=b"\x00")
        reassembler.clear()

        assert reassembler.get_complete_message(1) is None

    def test_reassemble_add_returns_true_when_complete(self) -> None:
        """add_fragment возвращает True когда все части собраны"""
        reassembler = SMSReassembler()

        assert reassembler.add_fragment(ref=1, total=2, seq=1, data=b"\x01") is False
        assert reassembler.add_fragment(ref=1, total=2, seq=2, data=b"\x02") is True


class TestAdapterSmsMethods:
    """Тесты на методы SMS в EgtsProtocol2015"""

    def setup_method(self) -> None:
        self.adapter = EgtsProtocol2015()

    def test_build_sms_pdu_basic(self) -> None:
        """Базовая сборка SMS PDU через адаптер"""
        egts_data = b"\x01\x02\x03\x04"
        pdu = self.adapter.build_sms_pdu(
            egts_packet_bytes=egts_data,
            destination="+79001234567",
        )

        result = parse_sms_pdu(pdu)
        assert result["user_data"] == egts_data
        assert result["sender"] == "+79001234567"

    def test_build_sms_pdu_with_smsc(self) -> None:
        """Сборка SMS PDU с SMSC через адаптер"""
        pdu = self.adapter.build_sms_pdu(
            egts_packet_bytes=b"\xAA",
            destination="+79001234567",
            smsc_number="+79009000900",
        )

        result = parse_sms_pdu(pdu)
        assert result["smsc"] == "+79009000900"

    def test_build_sms_pdu_concatenated(self) -> None:
        """Сборка конкатенированного SMS через адаптер"""
        pdu = self.adapter.build_sms_pdu(
            egts_packet_bytes=b"\xBB",
            destination="+79001234567",
            concatenated=True,
            concat_ref=5,
            concat_total=2,
            concat_seq=1,
        )

        result = parse_sms_pdu(pdu)
        assert result["concatenated"] is True
        assert result["concat_info"]["reference"] == 5

    def test_parse_sms_pdu_basic(self) -> None:
        """Базовый парсинг SMS PDU через адаптер"""
        original = b"\xDE\xAD\xBE\xEF"
        pdu = create_sms_pdu(
            phone_number="+79001234567",
            user_data=original,
        )

        result = self.adapter.parse_sms_pdu(pdu)
        assert result == original

    def test_adapter_version(self) -> None:
        """Версия адаптера"""
        assert self.adapter.version == "2015"

    def test_adapter_capabilities(self) -> None:
        """Адаптер поддерживает sms_pdu"""
        assert "sms_pdu" in self.adapter.capabilities
