"""EGTS — новая библиотека протокола (без дублирования, честный roundtrip)."""

import libs.egts._gost2015  # noqa: F401 — регистрирует ГОСТ 2015 при импорте
from libs.egts.models import Packet, ParseResult, Record, ResponseRecord, Subrecord
from libs.egts.protocol import IEgtsProtocol
from libs.egts.registry import get_protocol, register_version, available_versions
from libs.egts.types import (
    PACKET_HEADER_MIN_SIZE,
    TL_RECONNECT_TO,
    TL_RESEND_ATTEMPTS,
    TL_RESPONSE_TO,
    PacketType,
    ResultCode,
    ServiceType,
    SubrecordType,
)

__all__ = [
    'Packet',
    'PacketType',
    'ParseResult',
    'Record',
    'ResponseRecord',
    'ResultCode',
    'ServiceType',
    'Subrecord',
    'SubrecordType',
    'IEgtsProtocol',
    'get_protocol',
    'register_version',
    'available_versions',
    'PACKET_HEADER_MIN_SIZE',
    'TL_RESPONSE_TO',
    'TL_RESEND_ATTEMPTS',
    'TL_RECONNECT_TO',
]
