"""EGTS — новая библиотека протокола (без дублирования, честный roundtrip)."""

from libs.egts.types import PacketType, ServiceType, SubrecordType, ResultCode
from libs.egts.models import Packet, Record, Subrecord, ParseResult, ResponseRecord

__all__ = [
    'PacketType', 'ServiceType', 'SubrecordType', 'ResultCode',
    'Packet', 'Record', 'Subrecord', 'ParseResult', 'ResponseRecord',
]
