"""
Тесты на ECALL сервис EGTS (ГОСТ 33465-2015, раздел 7)

mypy: ignore-errors — тесты не типизируются (соглашение проекта).
"""

# mypy: ignore-errors
import pytest

from libs.egts_protocol_gost2015.gost2015_impl.services.ecall import (
    create_msd_data,
    create_track_point,
    parse_accel_data,
    parse_raw_msd_data,
    parse_track_data,
    serialize_accel_data,
    serialize_raw_msd_data,
    serialize_track_data,
)

# ============================================
# Тесты для ACCEL_DATA
# ============================================


class TestAccelData:
    """Тесты на подзапись ACCEL_DATA"""

    def test_accel_data_build(self):
        """Сборка ACCEL_DATA"""
        original_data = {
            "sa": 2,
            "atm": 1000000,
            "measurements": [
                {"rtm": 0, "xaav": 0.0, "yaav": 0.0, "zaav": -9.8},
                {"rtm": 100, "xaav": 5.0, "yaav": -2.0, "zaav": 1.0},
            ],
        }
        raw = serialize_accel_data(original_data)

        assert len(raw) >= 5 + 16  # SA + ATM + 2*8
        assert raw[0] == 2  # SA = 2

        parsed_data = parse_accel_data(raw)
        assert parsed_data["sa"] == 2
        assert parsed_data["atm"] == 1000000
        assert len(parsed_data["measurements"]) == 2

    def test_accel_data_parse(self):
        """Парсинг ACCEL_DATA"""
        # SA=1, ATM=1000, 1 измерение
        raw = b"\x01"  # SA
        raw += b"\xe8\x03\x00\x00"  # ATM=1000
        raw += b"\x00\x00"  # RTM=0
        raw += b"\x00\x00"  # XAAV=0
        raw += b"\x00\x00"  # YAAV=0
        raw += b"\xf4\xff"  # ZAAV=-12 (signed) → -1.2G

        parsed = parse_accel_data(raw)

        assert parsed["sa"] == 1
        assert parsed["atm"] == 1000
        assert len(parsed["measurements"]) == 1
        assert parsed["measurements"][0]["rtm"] == 0
        assert abs(parsed["measurements"][0]["zaav"] - (-1.2)) < 0.001

    def test_accel_data_roundtrip(self):
        """ACCEL_DATA: туда и обратно"""
        original_data = {
            "sa": 3,
            "atm": 2000000,
            "measurements": [
                {"rtm": 0, "xaav": 0.0, "yaav": 0.0, "zaav": -9.8},
                {"rtm": 50, "xaav": 10.0, "yaav": 0.0, "zaav": 0.0},
                {"rtm": 100, "xaav": 0.0, "yaav": -5.0, "zaav": 2.0},
            ],
        }
        raw = serialize_accel_data(original_data)
        parsed_data = parse_accel_data(raw)

        assert parsed_data["sa"] == original_data["sa"]
        assert parsed_data["atm"] == original_data["atm"]
        assert len(parsed_data["measurements"]) == 3

    def test_accel_data_invalid_size(self):
        """ACCEL_DATA: слишком маленькие данные"""
        with pytest.raises(ValueError, match="Слишком маленькие данные"):
            parse_accel_data(b"\x00" * 4)


# ============================================
# Тесты для RAW_MSD_DATA
# ============================================


class TestRawMsdData:
    """Тесты на подзапись RAW_MSD_DATA"""

    def test_raw_msd_data_build(self):
        """Сборка RAW_MSD_DATA с ASN.1 PER MSD"""
        try:
            msd = create_msd_data(
                vin="XTA12345678901234",
                latitude=55.751244,
                longitude=37.618423,
                vehicle_type=1,
                propulsion_type=0b000001,
                automatic_activation=True,
                timestamp=1710508245,
            )
        except RuntimeError:
            pytest.skip("asn1tools не установлен")

        original_data = {"fm": 1, "msd": msd}
        raw = serialize_raw_msd_data(original_data)

        assert raw[0] == 1  # FM
        assert len(raw) > 1

        parsed_data = parse_raw_msd_data(raw)
        assert parsed_data["fm"] == 1
        assert parsed_data["msd"] == msd

    def test_raw_msd_data_parse(self):
        """Парсинг RAW_MSD_DATA"""
        raw = b"\x01" + b"\xde\xad\xbe\xef"  # FM=1, MSD=data
        parsed = parse_raw_msd_data(raw)

        assert parsed["fm"] == 1
        assert parsed["msd"] == b"\xde\xad\xbe\xef"
        assert parsed["msd_len"] == 4

    def test_raw_msd_data_roundtrip(self):
        """RAW_MSD_DATA: туда и обратно"""
        msd = b"\x01\x02\x03\x04\x05"
        original_data = {"fm": 1, "msd": msd}
        raw = serialize_raw_msd_data(original_data)
        parsed_data = parse_raw_msd_data(raw)

        assert parsed_data["fm"] == original_data["fm"]
        assert parsed_data["msd"] == original_data["msd"]

    def test_raw_msd_data_invalid_size(self):
        """RAW_MSD_DATA: слишком маленькие данные"""
        with pytest.raises(ValueError, match="Слишком маленькие данные"):
            parse_raw_msd_data(b"")


# ============================================
# Тесты для TRACK_DATA (ГОСТ 33465 таблица 45)
# ============================================


class TestTrackData:
    """Тесты на подзапись TRACK_DATA"""

    def test_track_data_build(self):
        """Сборка TRACK_DATA"""
        original_data = {
            "sa": 2,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": 200704454, "lon": 135421235, "tnde": True},
                {"rtm": 5, "lat": 200704500, "lon": 135421300, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)

        assert raw[0] == 2  # SA = 2
        assert len(raw) >= 5 + 10  # SA + ATM + 2 точки

        parsed_data = parse_track_data(raw)
        assert parsed_data["sa"] == 2
        assert parsed_data["atm"] == 1000000
        assert len(parsed_data["track_points"]) == 2

    def test_track_data_with_speed_and_direction(self):
        """TRACK_DATA со скоростью и направлением"""
        original_data = {
            "sa": 1,
            "atm": 500000,
            "track_points": [
                {
                    "rtm": 0, "lat": 100, "lon": 200,
                    "spd": 50.0, "sd": 90, "tnde": True,
                },
            ],
        }
        raw = serialize_track_data(original_data)
        parsed_data = parse_track_data(raw)

        assert parsed_data["sa"] == 1
        assert len(parsed_data["track_points"]) == 1
        pt = parsed_data["track_points"][0]
        assert pt["lat"] == 100
        assert pt["lon"] == 200
        assert pt["spd"] == 50.0
        assert pt["sd"] == 90

    def test_track_data_roundtrip(self):
        """TRACK_DATA: туда и обратно"""
        original_data = {
            "sa": 3,
            "atm": 2000000,
            "track_points": [
                {"rtm": 0, "lat": 100, "lon": 200, "spd": 50.0, "sd": 90, "tnde": True},
                {"rtm": 5, "lat": 150, "lon": 250, "spd": 75.5, "sd": 128, "tnde": True},
                {"rtm": 10, "lat": 200, "lon": 300, "spd": 0.0, "sd": 64, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)
        parsed_data = parse_track_data(raw)

        assert parsed_data["sa"] == original_data["sa"]
        assert parsed_data["atm"] == original_data["atm"]
        assert len(parsed_data["track_points"]) == 3

        for i, (orig, parsed) in enumerate(zip(
            original_data["track_points"], parsed_data["track_points"], strict=False
        )):
            assert parsed["lat"] == orig["lat"], f"Точка {i}: LAT не совпадает"
            assert parsed["lon"] == orig["lon"], f"Точка {i}: LON не совпадает"
            assert abs(parsed["spd"] - orig["spd"]) < 0.02, f"Точка {i}: SPD не совпадает"
            assert parsed["sd"] == orig["sd"], f"Точка {i}: DIR не совпадает"

    def test_track_data_negative_coordinates(self):
        """TRACK_DATA с отрицательными координатами"""
        original_data = {
            "sa": 1,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": -100, "lon": -200, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)
        parsed_data = parse_track_data(raw)

        pt = parsed_data["track_points"][0]
        assert pt["lat"] == -100  # LAHS=1
        assert pt["lon"] == -200  # LOHS=1

    def test_track_data_invalid_size(self):
        """TRACK_DATA: слишком маленькие данные"""
        with pytest.raises(ValueError, match="Слишком маленькие данные"):
            parse_track_data(b"\x00" * 4)


# ============================================
# Тесты для create_track_point
# ============================================


class TestCreateTrackPoint:
    """Тесты на создание точек траектории"""

    def test_create_point_simple(self):
        """Создание простой точки"""
        point = create_track_point(rtm=5)

        assert point["rtm"] == 5
        assert "lat" not in point
        assert "lon" not in point

    def test_create_point_with_coordinates(self):
        """Создание точки с координатами"""
        point = create_track_point(rtm=2, latitude=55.75, longitude=37.61)

        assert point["rtm"] == 2
        assert "lat" in point
        assert "lon" in point
        # UINT32 modulus: lat / 90 * 0xFFFFFFFF
        assert point["lat"] > 0
        assert point["lon"] > 0

    def test_create_point_southern_hemisphere(self):
        """Создание точки с южной широтой (знак сохраняется)"""
        point = create_track_point(rtm=0, latitude=-33.92, longitude=151.21)

        # Южная широта должна быть отрицательной
        assert point["lat"] < 0
        # Восточная долгота положительная
        assert point["lon"] > 0

    def test_create_point_with_speed_and_direction(self):
        """Создание точки со скоростью и направлением"""
        point = create_track_point(rtm=0, speed=60.0, direction=180.0)

        assert "spd" in point
        assert "sd" in point
        assert point["spd"] == 60.0  # 60.00 км/ч
        assert 0 <= point["sd"] <= 511  # 9 бит

    def test_create_point_roundtrip(self):
        """create_track_point → serialize → parse → сверка"""
        point = create_track_point(
            rtm=3, latitude=55.75, longitude=37.61,
            speed=80.0, direction=270.0, tnde=True,
        )
        data = {"sa": 1, "atm": 1000000, "track_points": [point]}
        raw = serialize_track_data(data)
        parsed = parse_track_data(raw)

        pt = parsed["track_points"][0]
        assert abs(pt["lat"] - point["lat"]) <= 1  # Допуск из-за округления
        assert abs(pt["lon"] - point["lon"]) <= 1
        assert abs(pt["spd"] - point["spd"]) < 0.02
        # Направление может потерять младшие биты при конвертации
        assert abs(pt["sd"] - point["sd"]) <= 2


# ============================================
# Тесты для TNDE=0 (точка без координат)
# ============================================


class TestTrackDataTndeZero:
    """Тесты на точку без координат (TNDE=0, только RTM, 1 байт)"""

    def test_track_point_without_coordinates(self):
        """TRACK_DATA: точка без координат (TNDE=0, только RTM)"""
        original_data = {
            "sa": 1,
            "atm": 1000000,
            "track_points": [
                {"rtm": 3, "tnde": False},
            ],
        }
        raw = serialize_track_data(original_data)

        # SA(1) + ATM(4) + TDS(1) = 6 байт
        assert len(raw) == 6
        assert raw[0] == 1  # SA
        assert raw[5] == 0b000_00_011  # TNDE=0, LOHS=0, LAHS=0, SDFE=0, SPFE=0, RTM=3

        parsed = parse_track_data(raw)
        assert parsed["sa"] == 1
        assert len(parsed["track_points"]) == 1
        pt = parsed["track_points"][0]
        assert pt["rtm"] == 3
        assert pt["tnde"] is False
        assert "lat" not in pt
        assert "lon" not in pt

    def test_track_point_tnde_false_with_speed(self):
        """TRACK_DATA: TNDE=0 но со скоростью"""
        original_data = {
            "sa": 1,
            "atm": 500000,
            "track_points": [
                {"rtm": 1, "spd": 40.0, "tnde": False},
            ],
        }
        raw = serialize_track_data(original_data)
        parsed = parse_track_data(raw)

        pt = parsed["track_points"][0]
        assert pt["rtm"] == 1
        assert pt["tnde"] is False
        assert pt["spd"] == 40.0
        assert "lat" not in pt
        assert "lon" not in pt

    def test_track_mixed_tnde(self):
        """TRACK_DATA: смешанные точки — TNDE=1 с координатами и TNDE=1 без скорости"""
        original_data = {
            "sa": 2,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": 100, "lon": 200, "spd": 50.0, "sd": 90, "tnde": True},
                {"rtm": 5, "lat": 300, "lon": 400, "tnde": True},  # Без SPD/SD
            ],
        }
        raw = serialize_track_data(original_data)
        parsed = parse_track_data(raw)

        assert len(parsed["track_points"]) == 2
        # Первая точка: полная
        pt1 = parsed["track_points"][0]
        assert pt1["tnde"] is True
        assert "spd" in pt1
        assert "sd" in pt1
        # Вторая точка: только координаты без скорости
        pt2 = parsed["track_points"][1]
        assert pt2["tnde"] is True
        assert "spd" not in pt2
        assert "sd" not in pt2


# ============================================
# Тесты граничных значений (скорость, направление, координаты)
# ============================================


class TestTrackDataBoundary:
    """Тесты на граничные значения TRACK_DATA"""

    def test_max_speed_327_67_kmh(self):
        """TRACK_DATA: максимальная скорость 327,67 км/ч (15 бит = 0x7FFF)"""
        original_data = {
            "sa": 1,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": 100, "lon": 200, "spd": 327.67, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)
        parsed = parse_track_data(raw)

        pt = parsed["track_points"][0]
        assert abs(pt["spd"] - 327.67) < 0.02

    def test_max_direction_359_degrees(self):
        """TRACK_DATA: направление 359° (9 бит → 511) со скоростью"""
        original_data = {
            "sa": 1,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": 100, "lon": 200, "spd": 50.0, "sd": 511, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)
        parsed = parse_track_data(raw)

        pt = parsed["track_points"][0]
        assert pt["sd"] == 511  # 9 бит макс

    def test_max_coordinates_uint32(self):
        """TRACK_DATA: максимальные координаты UINT32"""
        original_data = {
            "sa": 1,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": 0xFFFFFFFF, "lon": 0xFFFFFFFF, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)
        parsed = parse_track_data(raw)

        pt = parsed["track_points"][0]
        assert pt["lat"] == 0xFFFFFFFF
        assert pt["lon"] == 0xFFFFFFFF


# ============================================
# Тесты LAHS/LOHS бинарной проверки
# ============================================


class TestLahsLohsBinary:
    """Тесты на явную проверку битов LAHS/LOHS в бинарном представлении"""

    def test_lahs_bit_in_serialized_bytes(self):
        """TRACK_DATA: LAHS=1 (южная широта) — бит 5 в TDS установлен"""
        original_data = {
            "sa": 1,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": -100, "lon": 200, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)

        # TDS байт: бит 5 = LAHS
        tds = raw[5]
        assert (tds >> 5) & 0x01 == 1  # LAHS=1

        parsed = parse_track_data(raw)
        pt = parsed["track_points"][0]
        assert pt["lahs"] is True
        assert pt["lohs"] is False

    def test_lohs_bit_in_serialized_bytes(self):
        """TRACK_DATA: LOHS=1 (западная долгота) — бит 6 в TDS установлен"""
        original_data = {
            "sa": 1,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": 100, "lon": -200, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)

        # TDS байт: бит 6 = LOHS
        tds = raw[5]
        assert (tds >> 6) & 0x01 == 1  # LOHS=1

        parsed = parse_track_data(raw)
        pt = parsed["track_points"][0]
        assert pt["lahs"] is False
        assert pt["lohs"] is True

    def test_zero_coordinates_lahs_lohs_clear(self):
        """TRACK_DATA: lat=0, lon=0 — LAHS=0, LOHS=0"""
        original_data = {
            "sa": 1,
            "atm": 1000000,
            "track_points": [
                {"rtm": 0, "lat": 0, "lon": 0, "tnde": True},
            ],
        }
        raw = serialize_track_data(original_data)

        tds = raw[5]
        assert (tds >> 5) & 0x01 == 0  # LAHS=0
        assert (tds >> 6) & 0x01 == 0  # LOHS=0

        parsed = parse_track_data(raw)
        pt = parsed["track_points"][0]
        assert pt["lat"] == 0
        assert pt["lon"] == 0
        assert pt["lahs"] is False
        assert pt["lohs"] is False
