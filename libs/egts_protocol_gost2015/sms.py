"""
Модуль для работы с SMS в режиме PDU (ГОСТ 33465-2015, раздел 5.7)

SMS используется как резервный канал передачи данных протокола EGTS.

Основные возможности:
- Создание SMS PDU для отправки пакетов EGTS
- Парсинг полученных SMS PDU
- Поддержка конкатенации SMS для пакетов > 140 байт
- Поддержка команд EGTS_ECALL_REQ и EGTS_ECALL_MSD_REQ

Пример использования:
    from libs.egts_protocol_gost2015.sms import create_sms_pdu, parse_sms_pdu

    # Создание SMS для отправки пакета EGTS
    pdu = create_sms_pdu(
        phone_number="+79001234567",
        user_data=packet_bytes,
        smsc_number="+79009000900"
    )

    # Парсинг полученного SMS
    result = parse_sms_pdu(pdu)
    egts_data = result["user_data"]
"""

from typing import Any

# ============================================
# Константы и типы данных
# ============================================


class SMSTypeOfNumber:
    """Тип номера (TON - Type Of Number) по ГОСТ 33465, таблица 9"""

    UNKNOWN = 0b000
    INTERNATIONAL = 0b001
    NATIONAL = 0b010
    NETWORK_SPECIFIC = 0b011
    SUBSCRIBER = 0b100
    ALPHANUMERIC = 0b101
    ABBREVIATED = 0b110
    RESERVED = 0b111


class SMSNumberingPlan:
    """План нумерации (NPI - Numeric Plan Identification) по ГОСТ 33465, таблица 9"""

    UNKNOWN = 0b0000
    ISDN_TELEPHONY = 0b0001
    DATA = 0b0011
    TELEX = 0b0100
    NATIONAL = 0b1000
    PRIVATE = 0b1001
    RESERVED = 0b1111


class SMSDataCodingScheme:
    """Кодировка данных SMS (TP_DCS)"""

    BINARY_8BIT = 0x04  # 8-битная кодировка без компрессии


class SMSMessageClass:
    """Класс SMS сообщения"""

    CLASS_0 = 0x00  # Flash SMS
    CLASS_1 = 0x01  # Normal SMS
    CLASS_2 = 0x02  # SIM specific
    CLASS_3 = 0x03  # Terminal specific


# Информационные элементы заголовка пользовательских данных
IEI_CONCATENATED_MESSAGE = 0x00  # Часть конкатенируемого сообщения
IEI_SPECIAL_MESSAGE = 0x01  # Индикатор специального сообщения


# ============================================
# Вспомогательные функции
# ============================================


def _encode_phone_number(phone: str, for_smsc: bool = False) -> tuple[int, bytes]:
    """
    Кодирование телефонного номера в формат SMS

    Args:
        phone: Номер телефона (например, "+79001234567" или "9001234567")
        for_smsc: Если True, длина возвращается в октетах (для SMSC),
                  иначе в полуоктетах (для TP-DA/TP-OA)

    Returns:
        Tuple с длиной адреса и закодированными байтами номера
        (включая байт типа адреса)
    """
    # Удаляем лишние символы
    clean_phone = phone.strip().replace(" ", "").replace("-", "")

    # Определяем тип номера и план нумерации автоматически
    ton = SMSTypeOfNumber.INTERNATIONAL  # По умолчанию международный
    npi = SMSNumberingPlan.ISDN_TELEPHONY  # ISDN/телефония

    if clean_phone.startswith("+"):
        ton = SMSTypeOfNumber.INTERNATIONAL
        clean_phone = clean_phone[1:]
    elif clean_phone.startswith("8"):
        # Российский номер, начинающийся с 8 - национальный
        ton = SMSTypeOfNumber.NATIONAL
        clean_phone = clean_phone[1:]

    # Кодируем цифры в полуоктеты
    # Каждая цифра кодируется 4 битами
    # Нечетные цифры идут в младшие 4 бита, четные - в старшие
    encoded = bytearray()

    for i in range(0, len(clean_phone), 2):
        digit1 = clean_phone[i]
        digit2 = clean_phone[i + 1] if i + 1 < len(clean_phone) else "F"

        # Преобразуем символы в числовые значения
        val1 = int(digit1) if digit1.isdigit() else 0x0F
        val2 = int(digit2) if digit2.isdigit() else 0x0F

        # Упаковываем в байт (младшая цифра в младших 4 битах)
        encoded.append((val1 & 0x0F) | ((val2 & 0x0F) << 4))

    # Количество цифр
    num_digits = len(phone.replace("+", "").replace(" ", "").replace("-", ""))

    # Байт типа адреса: бит 7 = 0, биты 6-4 = TON, бит 3 = 0, биты 2-0 = NPI
    type_byte = bytes([((ton & 0x07) << 4) | (npi & 0x0F)])

    # Для SMSC длина указывается в октетах (байтах) полезных данных
    # Для TP-DA/TP-OA длина указывается в полуоктетах (цифрах)
    if for_smsc:
        # Длина = 1 (байт типа) + ceil(num_digits / 2)
        address_length = 1 + (len(encoded))
    else:
        # Длина в полуоктетах = количеству цифр
        address_length = num_digits

    return address_length, type_byte + bytes(encoded)


def _decode_phone_number(data: bytes, length: int, ton: int, npi: int) -> str:
    """
    Декодирование телефонного номера из формата SMS

    Args:
        data: Закодированные байты номера
        length: Длина адреса в полуоктетах
        ton: Type of Number
        npi: Numbering Plan Identification

    Returns:
        Строка с номером телефона
    """
    digits = []

    for byte in data:
        # Младшие 4 бита
        digit1 = byte & 0x0F
        # Старшие 4 бита
        digit2 = (byte >> 4) & 0x0F

        if digit1 <= 9:
            digits.append(str(digit1))
        if digit2 <= 9 and len(digits) < length:
            digits.append(str(digit2))

    phone = "".join(digits)

    # Добавляем префикс в зависимости от TON
    if ton == SMSTypeOfNumber.INTERNATIONAL:
        phone = "+" + phone

    return phone


# ============================================
# Создание SMS PDU
# ============================================


def create_sms_pdu(
    phone_number: str,
    user_data: bytes,
    smsc_number: str = "",
    message_reference: int = 0,
    request_status_report: bool = False,
    concatenated: bool = False,
    concat_ref: int = 0,
    concat_total: int = 1,
    concat_seq: int = 1,
) -> bytes:
    """
    Создание SMS PDU для отправки (режим PDU по ГОСТ 33465, таблица 8)

    Args:
        phone_number: Номер получателя (например, "+79001234567")
        user_data: Пользовательские данные (пакет EGTS)
        smsc_number: Номер SMSC (если пустой, используется из SIM-карты)
        message_reference: Идентификатор сообщения (TP_MR), увеличивается на 1 для каждого нового SMS
        request_status_report: Запросить подтверждение доставки (TP_SRR)
        concatenated: Использовать конкатенацию (для длинных сообщений)
        concat_ref: Номер конкатенируемого сообщения (CSMRN)
        concat_total: Общее количество частей (MNSM)
        concat_seq: Номер текущей части (SNCSM)

    Returns:
        Байты SMS PDU для отправки в модем
    """
    result = bytearray()

    # ============================================
    # SMSC Address (опционально)
    # ============================================
    if smsc_number:
        # Кодируем номер SMSC (for_smsc=True т.к. длина в октетах)
        smsc_len, smsc_encoded = _encode_phone_number(smsc_number, for_smsc=True)
        # SMSC_AL = длина полезных данных (октеты) = smsc_len - 1 (без учета байта длины)
        # Но smsc_len уже включает только полезные данные (тип + номер)
        result.append(smsc_len)
        result.extend(smsc_encoded)
    else:
        # SMSC из SIM-карты
        result.append(0x00)

    # ============================================
    # TP-MTI (Type of Message) + флаги
    # ============================================
    # TP_MTI = 01 (SMS Deliver для исходящих)
    # TP_RD = 0 (не отклонять дубликаты)
    # TP_VPF = 00 (VP не передается)
    # TP_SRR = 1 если нужен статус отчет
    # TP_UDHI = 1 если есть заголовок пользовательских данных
    # TP_RP = 0 (нет reply path)
    tp_mti = 0x01  # SMS-SUBMIT

    # Бит 6 = 0x40 - TP_UDHI (User Data Header Indicator)
    tp_udhi = 0x40 if (concatenated or (user_data and len(user_data) > 140)) else 0x00
    # Бит 2 = 0x04 - TP_SRR (Status Report Request)
    tp_srr = 0x04 if request_status_report else 0x00

    first_byte = tp_mti | tp_udhi | tp_srr
    result.append(first_byte)

    # ============================================
    # TP-Message-Reference (TP-MR)
    # ============================================
    result.append(message_reference & 0xFF)

    # ============================================
    # TP-Destination-Address (TP-DA)
    # ============================================
    da_len, da_encoded = _encode_phone_number(phone_number)
    result.append(da_len)  # TP_DA_L
    result.extend(da_encoded)  # TP_DA_T + TP_DA

    # ============================================
    # TP-Protocol-Identifier (TP-PID)
    # ============================================
    result.append(0x00)  # Обычный SMS

    # ============================================
    # TP-Data-Coding-Scheme (TP-DCS)
    # ============================================
    result.append(SMSDataCodingScheme.BINARY_8BIT)  # 8-битная кодировка

    # ============================================
    # TP-Validity-Period (TP-VP) - не передается
    # ============================================

    # ============================================
    # Заголовок пользовательских данных (UDH)
    # ============================================
    udh = bytearray()

    if concatenated:
        # Информационный элемент конкатенации (3 байта данных)
        # IEI = 0x00 (Concatenated Message)
        # LIE = 0x03 (длина данных IE)
        # IED = [CSMRN, MNSM, SNCSM]
        udh.append(IEI_CONCATENATED_MESSAGE)
        udh.append(0x03)  # Длина данных IE
        udh.append(concat_ref & 0xFF)  # Reference number
        udh.append(concat_total & 0xFF)  # Total messages
        udh.append(concat_seq & 0xFF)  # Sequence number

    # ============================================
    # TP-User-Data
    # ============================================
    # Если есть UDH, добавляем LUDH (длина заголовка) перед ним
    if udh:
        # LUDH + UDH + пользовательские данные
        user_data_full = bytes([len(udh)]) + udh + user_data
    else:
        user_data_full = user_data

    # TP-User-Data-Length - длина в октетах
    total_ud_length = len(user_data_full)
    result.append(total_ud_length)

    # Добавляем пользовательские данные (включая UDH если есть)
    if user_data_full:
        result.extend(user_data_full)

    return bytes(result)


# ============================================
# Парсинг SMS PDU
# ============================================


def parse_sms_pdu(pdu: bytes) -> dict[str, Any]:
    """
    Парсинг SMS PDU (режим PDU по ГОСТ 33465, таблица 8)

    Args:
        pdu: Байты SMS PDU

    Returns:
        Dict с полями:
        - smsc: Номер SMSC (или None если из SIM)
        - sender: Номер отправителя
        - user_data: Пользовательские данные
        - message_reference: Идентификатор сообщения
        - concatenated: Флаг конкатенации
        - concat_info: Информация о конкатенации (ref, total, seq)
        - status_report_requested: Запрошен ли статус отчет
    """
    if len(pdu) < 12:
        raise ValueError(f"Слишком короткие данные SMS PDU: {len(pdu)} байт (минимум 12)")

    offset = 0
    result: dict[str, Any] = {
        "smsc": None,
        "sender": None,
        "user_data": b"",
        "message_reference": 0,
        "concatenated": False,
        "concat_info": None,
        "status_report_requested": False,
    }

    # ============================================
    # SMSC Address
    # ============================================
    smsc_al = pdu[offset]
    offset += 1

    if smsc_al > 0:
        smsc_at = pdu[offset]
        offset += 1
        smsc_ton = (smsc_at >> 4) & 0x07
        smsc_npi = smsc_at & 0x0F

        # Для SMSC длина указывается в октетах (байтах) полезных данных
        # smsc_al = длина SMSC_AT + SMSC_A (в байтах)
        # Поэтому длина данных = smsc_al - 1 (без учета байта типа)
        smsc_data_len = smsc_al - 1
        smsc_data = pdu[offset : offset + smsc_data_len]
        offset += smsc_data_len

        # Для декодирования передаем длину в полуоктетах (цифрах)
        # Количество цифр = (количество байт * 2) - 1 если последний байт имеет filler
        num_digits = smsc_data_len * 2
        if smsc_data and (smsc_data[-1] >> 4) == 0x0F:
            num_digits -= 1  # Последний nibble - filler

        result["smsc"] = _decode_phone_number(smsc_data, num_digits, smsc_ton, smsc_npi)

    # ============================================
    # TP-MTI + флаги
    # ============================================
    tp_flags = pdu[offset]
    offset += 1

    _tp_mti = tp_flags & 0x03
    tp_udhi = bool((tp_flags >> 6) & 0x01)
    tp_srr = bool((tp_flags >> 2) & 0x01)

    result["status_report_requested"] = tp_srr

    # ============================================
    # TP-Message-Reference
    # ============================================
    result["message_reference"] = pdu[offset]
    offset += 1

    # ============================================
    # TP-Originating-Address (TP-OA)
    # ============================================
    oa_len = pdu[offset]
    offset += 1
    oa_at = pdu[offset]
    offset += 1
    oa_ton = (oa_at >> 4) & 0x07
    oa_npi = oa_at & 0x0F

    # Длина в байтах = (длина в полуоктетах + 1) // 2
    oa_data_len = (oa_len + 1) // 2
    oa_data = pdu[offset : offset + oa_data_len]
    offset += oa_data_len

    result["sender"] = _decode_phone_number(oa_data, oa_len, oa_ton, oa_npi)

    # ============================================
    # TP-Protocol-Identifier
    # ============================================
    offset += 1  # TP-PID

    # ============================================
    # TP-Data-Coding-Scheme
    # ============================================
    offset += 1  # TP-DCS

    # ============================================
    # TP-Validity-Period (опционально)
    # ============================================
    # Не обрабатываем для простоты

    # ============================================
    # TP-User-Data-Length
    # ============================================
    if offset >= len(pdu):
        # Нет данных о длине пользовательских данных
        return result

    _ud_len = pdu[offset]
    offset += 1

    # ============================================
    # TP-User-Data-Header (опционально)
    # ============================================
    if tp_udhi and offset < len(pdu):
        # LUDH - длина заголовка
        if offset >= len(pdu):
            return result

        ludh = pdu[offset]
        offset += 1

        # Парсим информационные элементы
        udh_end = offset + ludh

        while offset < udh_end and offset < len(pdu):
            if offset >= len(pdu):
                break

            iei = pdu[offset]  # Information Element Identifier
            offset += 1

            if offset >= len(pdu):
                break

            lie = pdu[offset]  # Length of Information Element
            offset += 1

            if offset + lie > len(pdu):
                break

            ied = pdu[offset : offset + lie]
            offset += lie

            # Обрабатываем конкатенацию
            if iei == IEI_CONCATENATED_MESSAGE and len(ied) >= 3:
                result["concatenated"] = True
                result["concat_info"] = {
                    "reference": ied[0],
                    "total": ied[1],
                    "sequence": ied[2],
                }

    # ============================================
    # TP-User-Data
    # ============================================
    remaining = len(pdu) - offset
    if remaining > 0:
        result["user_data"] = pdu[offset : offset + remaining]

    return result


# ============================================
# Конкатенация SMS
# ============================================


def split_for_sms_concatenation(
    data: bytes, max_part_size: int = 134
) -> list[tuple[int, int, int, bytes]]:
    """
    Разбиение данных на части для конкатенации SMS

    Согласно ГОСТ 33465-2015 (раздел 5.7.2.3):
    - Максимальный размер одного SMS: 140 байт
    - Заголовок конкатенации: 6 байт (LUDH + IEI + LIE + 3 байта данных)
    - Доступно для данных: 140 - 6 = 134 байта
    - Максимальное количество частей: 255
    - Максимальный размер пакета EGTS: 1360 байт (ограничение УСВ)

    Args:
        data: Данные для разбиения (пакет EGTS)
        max_part_size: Максимальный размер данных в одной части (по умолчанию 134)

    Returns:
        Список кортежей (concat_ref, total_parts, seq_num, part_data)
    """
    if len(data) == 0:
        return []

    # Генерируем случайный reference для этого сообщения
    import random

    concat_ref = random.randint(0, 255)

    # Разбиваем данные на части
    parts = []
    total_parts = (len(data) + max_part_size - 1) // max_part_size

    for i in range(0, len(data), max_part_size):
        seq_num = (i // max_part_size) + 1
        part_data = data[i : i + max_part_size]
        parts.append((concat_ref, total_parts, seq_num, part_data))

    return parts


def create_concatenated_sms_list(
    phone_number: str,
    egts_packet: bytes,
    smsc_number: str = "",
    message_reference: int = 0,
    request_status_report: bool = True,
) -> list[bytes]:
    """
    Создание списка SMS PDU для конкатенированного сообщения

    Args:
        phone_number: Номер получателя
        egts_packet: Пакет EGTS для отправки
        smsc_number: Номер SMSC
        message_reference: Идентификатор сообщения
        request_status_report: Запросить подтверждение доставки

    Returns:
        Список байтов SMS PDU для каждой части
    """
    # Разбиваем пакет на части
    parts = split_for_sms_concatenation(egts_packet)

    sms_list = []
    for concat_ref, total_parts, seq_num, part_data in parts:
        pdu = create_sms_pdu(
            phone_number=phone_number,
            user_data=part_data,
            smsc_number=smsc_number,
            message_reference=message_reference,
            request_status_report=request_status_report,
            concatenated=True,
            concat_ref=concat_ref,
            concat_total=total_parts,
            concat_seq=seq_num,
        )
        sms_list.append(pdu)

    return sms_list


# ============================================
# Сборка конкатенированных SMS
# ============================================


class SMSReassembler:
    """
    Класс для сборки конкатенированных SMS сообщений

    Пример использования:
        reassembler = SMSReassembler()

        # Для каждого полученного SMS
        if result["concatenated"]:
            reassembler.add_fragment(
                ref=result["concat_info"]["reference"],
                total=result["concat_info"]["total"],
                seq=result["concat_info"]["sequence"],
                data=result["user_data"]
            )

            # Проверяем, собрано ли сообщение полностью
            complete_data = reassembler.get_complete_message(ref)
            if complete_data:
                print(f"Сообщение собрано: {len(complete_data)} байт")
    """

    def __init__(self):
        self._fragments: dict[int, dict[str, Any]] = {}

    def add_fragment(
        self, ref: int, total: int, seq: int, data: bytes
    ) -> bool:
        """
        Добавление фрагмента конкатенированного сообщения

        Args:
            ref: Reference number сообщения
            total: Общее количество частей
            seq: Номер текущей части
            data: Данные фрагмента

        Returns:
            True если все фрагменты собраны
        """
        if ref not in self._fragments:
            self._fragments[ref] = {
                "total": total,
                "parts": {},
            }

        self._fragments[ref]["parts"][seq] = data

        # Проверяем, все ли части получены
        received = len(self._fragments[ref]["parts"])
        return received >= total

    def get_complete_message(self, ref: int) -> bytes | None:
        """
        Получение собранного сообщения

        Args:
            ref: Reference number сообщения

        Returns:
            Байты собранного сообщения или None если не все части получены
        """
        if ref not in self._fragments:
            return None

        frag_info = self._fragments[ref]
        total = frag_info["total"]
        parts = frag_info["parts"]

        # Проверяем, все ли части получены
        if len(parts) < total:
            return None

        # Собираем части по порядку
        result = bytearray()
        for seq in range(1, total + 1):
            if seq in parts:
                result.extend(parts[seq])
            else:
                return None  # Нет нужной части

        # Очищаем память
        del self._fragments[ref]

        return bytes(result)

    def clear(self) -> None:
        """Очистка всех собранных фрагментов"""
        self._fragments.clear()

    def remove_expired(self, max_ref: int = 255) -> None:
        """
        Удаление старых сообщений (при переполнении reference)

        Args:
            max_ref: Максимальный reference number
        """
        # При переполнении reference (0-255) удаляем старые сообщения
        if len(self._fragments) > max_ref:
            self.clear()


# ============================================
# Экспорт основных функций
# ============================================

__all__ = [
    "SMSDataCodingScheme",
    "SMSNumberingPlan",
    "SMSReassembler",
    "SMSTypeOfNumber",
    "create_concatenated_sms_list",
    "create_sms_pdu",
    "parse_sms_pdu",
    "split_for_sms_concatenation",
]
