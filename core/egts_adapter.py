"""Адаптер новой EGTS библиотеки для ядра проекта.

Связывает libs.egts с core/ — заменяет libs.egts_protocol_iface.
"""

import logging

import libs.egts._gost2015  # noqa: F401 — регистрирует протокол
from libs.egts.models import ParseResult
from libs.egts.protocol import IEgtsProtocol
from libs.egts.registry import get_protocol
from libs.egts.types import ResultCode

logger = logging.getLogger(__name__)

# Константы для обратной совместимости
EGTS_PC_OK = ResultCode.OK.value
EGTS_PC_IN_PROGRESS = ResultCode.IN_PROGRESS.value
EGTS_PC_UNS_PROTOCOL = ResultCode.UNS_PROTOCOL.value
EGTS_PC_DECRYPT_ERROR = ResultCode.DECRYPT_ERROR.value
EGTS_PC_PROC_DENIED = ResultCode.PROC_DENIED.value
EGTS_PC_INC_HEADERFORM = ResultCode.INC_HEADERFORM.value
EGTS_PC_INC_DATAFORM = ResultCode.INC_DATAFORM.value
EGTS_PC_UNS_TYPE = ResultCode.UNS_TYPE.value
EGTS_PC_NOTEN_PARAMS = ResultCode.NOTEN_PARAMS.value
EGTS_PC_DBL_PROC = ResultCode.DBL_PROC.value
EGTS_PC_PROC_SRC_DENIED = ResultCode.PROC_SRC_DENIED.value
EGTS_PC_HEADERCRC_ERROR = ResultCode.HEADERCRC_ERROR.value
EGTS_PC_DATACRC_ERROR = ResultCode.DATACRC_ERROR.value
EGTS_PC_INVDATALEN = ResultCode.INVDATALEN.value
EGTS_PC_ROUTE_NFOUND = ResultCode.ROUTE_NFOUND.value
EGTS_PC_ROUTE_CLOSED = ResultCode.ROUTE_CLOSED.value
EGTS_PC_ROUTE_DENIED = ResultCode.ROUTE_DENIED.value
EGTS_PC_INVADDR = ResultCode.INVADDR.value
EGTS_PC_TTLEXPIRED = ResultCode.TTLEXPIRED.value
EGTS_PC_NO_ACK = ResultCode.NO_ACK.value
EGTS_PC_OBJ_NFOUND = ResultCode.OBJ_NFOUND.value
EGTS_PC_EVNT_NFOUND = ResultCode.EVNT_NFOUND.value
EGTS_PC_SRVC_NFOUND = ResultCode.SRVC_NFOUND.value
EGTS_PC_SRVC_DENIED = ResultCode.SRVC_DENIED.value
EGTS_PC_SRVC_UNKN = ResultCode.SRVC_UNKN.value
EGTS_PC_AUTH_DENIED = ResultCode.AUTH_DENIED.value
EGTS_PC_ALREADY_EXISTS = ResultCode.ALREADY_EXISTS.value
EGTS_PC_ID_NFOUND = ResultCode.ID_NFOUND.value
EGTS_PC_INC_DATETIME = ResultCode.INC_DATETIME.value

# Минимальный размер заголовка
PACKET_HEADER_MIN_SIZE = 11

# Таймауты (перенесены из iface)
TL_RESPONSE_TO = 5
TL_RESEND_ATTEMPTS = 3
TL_RECONNECT_TO = 30


def create_protocol(version: str = "2015") -> IEgtsProtocol:
    """Создать экземпляр протокола (обратная совместимость)."""
    return get_protocol(version)  # type: ignore[no-any-return]

def collect_extra(parsed: ParseResult) -> dict[str, object]:
    """Собрать flat dict из ParseResult для обратной совместимости.

    Заменяет старое поле extra — собирает данные из всех subrecord.data.
    """
    result: dict[str, object] = {}
    if parsed.packet is None:
        return result

    for rec in parsed.packet.records:
        for sr in rec.subrecords:
            if isinstance(sr.data, dict):
                result.update(sr.data)

    return result
