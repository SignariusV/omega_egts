"""
Подзапись уровня поддержки услуг EGTS (ГОСТ 33465-2015, раздел 6.6.3)

Подзапись состоит из:
- SRT (1 байт) - тип подзаписи
- SRL (2 байта) - длина данных SRD
- SRD (0-65495 байт) - данные подзаписи
"""

from dataclasses import dataclass, field
from typing import Any

from .types import MAX_SUBRECORD_SIZE, MIN_SUBRECORD_SIZE, SRL_SIZE, SRT_SIZE, SUBRECORD_HEADER_SIZE


@dataclass
class Subrecord:
    """
    Подзапись уровня поддержки услуг

    Attributes:
        subrecord_type: Тип подзаписи (SRT, 1 байт)
        data: Данные подзаписи (SRD) - байты или распарсенный dict
        raw_data: Исходные байты данных (для парсинга)
    """

    subrecord_type: int
    data: Any = None  # bytes или Dict[str, Any]
    raw_data: bytes = field(default_factory=bytes, repr=False)

    def to_bytes(self) -> bytes:
        """
        Сериализация подзаписи в байты

        Returns:
            bytes: Подзапись с заголовком и данными

        Raises:
            ValueError: Если длина SRD превышает MAX_SUBRECORD_SIZE
            NotImplementedError: Если data — dict, но raw_data отсутствует
        """
        # Определяем данные для сериализации
        if isinstance(self.data, bytes):
            srd = self.data
        elif isinstance(self.data, dict):
            # Для dict-данных требуется внешний сериализатор
            if self.raw_data:
                srd = self.raw_data
            else:
                raise NotImplementedError(
                    "Сериализация dict-данных требует внешнего сериализатора. "
                    "Установите raw_data или используйте bytes для data."
                )
        elif self.data is None:
            srd = self.raw_data
        else:
            srd = bytes(self.data) if self.data else b""

        # Валидация максимальной длины SRD
        if len(srd) > MAX_SUBRECORD_SIZE:
            raise ValueError(
                f"Превышен максимальный размер SRD: {len(srd)} байт "
                f"(макс. {MAX_SUBRECORD_SIZE} по ГОСТ 33465-2015)"
            )

        # SRT (1 байт)
        header = bytes([self.subrecord_type])

        # SRL (2 байта) - длина данных SRD
        header += len(srd).to_bytes(2, "little")

        # SRD (данные)
        return header + srd

    @classmethod
    def from_bytes(cls, data: bytes) -> "Subrecord":
        """
        Парсинг подзаписи из байтов

        Args:
            data: Байты подзаписи (начиная с SRT)

        Returns:
            Subrecord: Распарсенная подзапись

        Raises:
            ValueError: Если данные меньше минимального размера, SRL превышает
                        MAX_SUBRECORD_SIZE или данных недостаточно для SRD
        """
        if len(data) < SUBRECORD_HEADER_SIZE:
            raise ValueError(f"Слишком маленькая подзапись: {len(data)} байт (минимум {MIN_SUBRECORD_SIZE})")

        offset = 0

        # SRT (1 байт)
        subrecord_type = data[offset]
        offset += SRT_SIZE

        # SRL (2 байта) - длина данных SRD
        srl = int.from_bytes(data[offset : offset + SRL_SIZE], "little")
        offset += SRL_SIZE

        # Валидация размера SRD
        if srl > MAX_SUBRECORD_SIZE:
            raise ValueError(
                f"Превышен максимальный размер SRD: {srl} > {MAX_SUBRECORD_SIZE} (ГОСТ 33465-2015)"
            )

        # Проверка наличия достаточного количества данных
        if offset + srl > len(data):
            raise ValueError(
                f"Недостаточно данных для SRD: ожидается {srl}, доступно {len(data) - offset}"
            )

        # SRD (данные)
        srd = data[offset : offset + srl]

        return cls(
            subrecord_type=subrecord_type,
            data=srd,  # Пока сохраняем как bytes
            raw_data=srd,
        )


def parse_subrecords(data: bytes, service_type: int) -> list[Subrecord]:
    """
    Парсинг списка подзаписей из данных записи

    Args:
        data: Байты данных записи (RD)
        service_type: Тип сервиса для определения формата подзаписей
            (используется на более высоких уровнях парсинга, пока не применяется)

    Returns:
        List[Subrecord]: Список распарсенных подзаписей

    Raises:
        ValueError: Если SRL превышает MAX_SUBRECORD_SIZE или данных недостаточно
    """
    subrecords = []
    offset = 0

    while offset < len(data):
        if offset + SUBRECORD_HEADER_SIZE > len(data):
            raise ValueError(
                f"Недостаточно данных для заголовка подзаписи: "
                f"доступно {len(data) - offset} байт, требуется {SUBRECORD_HEADER_SIZE}"
            )

        # SRT (1 байт)
        srt = data[offset]
        offset += SRT_SIZE

        # SRL (2 байта)
        srl = int.from_bytes(data[offset : offset + SRL_SIZE], "little")
        offset += SRL_SIZE

        # Валидация размера SRD
        if srl > MAX_SUBRECORD_SIZE:
            raise ValueError(
                f"Превышен максимальный размер SRD: {srl} > {MAX_SUBRECORD_SIZE} (ГОСТ 33465-2015)"
            )

        # SRD (данные)
        if offset + srl > len(data):
            raise ValueError(
                f"Недостаточно данных для SRD: ожидается {srl}, доступно {len(data) - offset}"
            )

        srd = data[offset : offset + srl]
        offset += srl

        subrecord = Subrecord(
            subrecord_type=srt,
            data=srd,
            raw_data=srd,
        )
        subrecords.append(subrecord)

    return subrecords


def serialize_subrecords(subrecords: list[Subrecord]) -> bytes:
    """
    Сериализация списка подзаписей в байты

    Args:
        subrecords: Список подзаписей

    Returns:
        bytes: Байты данных записи (RD)
    """
    data = b""
    for subrecord in subrecords:
        data += subrecord.to_bytes()
    return data
