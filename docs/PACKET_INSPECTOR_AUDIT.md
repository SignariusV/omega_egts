# Аудит кода пакетного инспектора

**Дата:** 2026-06-01
**Область:** `gui/dashboard/cards/packet_detail.py`, `gui/utils/byte_layout.py`, `gui/utils/hex_viewer.py`, `gui/dashboard/cards/live_packets.py`
**Тестовое покрытие:** 45/45 тестов проходит (`tests/gui/cards/test_packet_detail.py`, `tests/gui/utils/test_byte_layout.py`, `tests/gui/utils/test_hex_viewer.py`)

---

## Резюме

Проведён построчный анализ трёх ключевых файлов пакетного инспектора. Выявлено **5 критических багов** (неправильные вычисления, приводящие к некорректному отображению данных), **1 пропуск функциональности** по спецификации ГОСТ, **3 проблемы несогласованности** и **4 замечания к качеству кода**. Текущее покрытие тестами не выявляет ни один из критических багов — они находятся в кодовых путях, для которых нет тестов (SRT 33, 34, ACCEL_DATA, TRACK_DATA, полный цикл APPDATA с несколькими записями).

---

## 🔴 P0 — Критические баги

### Б-01. `_parse_srt_33` всегда показывает OD-поле размером 6 байт

**Файл:** `gui/utils/byte_layout.py:876`
**Функция:** `EGTS_SR_SERVICE_PART_DATA` (частичная передача данных ПО)

```python
# Строка 876:
remaining = _len - (offset - (offset - _len + 6))
```

`offset` сокращается, и выражение упрощается до `remaining = _len - (_len - 6) = 6`. Вместо реального количества оставшихся байт **всегда возвращается 6**. При `_len < 6` (что невозможно из-за guard `if _len < 8: return` на 851) выражение даст отрицательное значение, а при `_len > 6` пользователь увидит неверный размер поля OD.

**Воспроизведение:** Любой пакет SRT=33 длиной > 6 байт (ID+PN+EPQ+ODH+OD) покажет OD как 6 байт.

**Исправление:**
```python
def _parse_srt_33(data: bytes, offset: int, _len: int) -> list[ByteField]:
    fields = []
    start = offset  # ← сохранить начальную позицию
    if _len < 8:
        return fields
    # ... (ID, PN, EPQ) ...
    if pn == 1 and (_len - 6) > 0:
        # ODH parsing ...
        offset = odh_end
    remaining = _len - (offset - start)  # ← корректное вычисление
    if remaining > 0:
        fields.append(_make_field("OD", offset, offset + remaining - 1,
                                  data[offset:offset + remaining],
                                  f"({remaining} bytes)", field_type="subrecord_data"))
    return fields
```

**Тест:** отсутствует для SRT 33.

---

### Б-02. `_parse_srt_34` никогда не показывает OD-поле

**Файл:** `gui/utils/byte_layout.py:896`
**Функция:** `EGTS_SR_SERVICE_FULL_DATA` (полная передача данных ПО)

```python
# Строка 896:
remaining = _len - (odh_end - (odh_end - _len))
```

Упрощается: `odh_end - (odh_end - _len) = _len`, поэтому `remaining = 0`. **OD-поле (тело прошивки) никогда не отображается в дереве полного обновления ПО.** В hex viewer байты видны, но в дереве полей — нет, что критично при анализе прошивок.

**Воспроизведение:** Любой пакет SRT=34 → отсутствие OD в дереве протокола.

**Исправление:** аналогично Б-01:
```python
start = offset
# ... (ODH parsing) ...
remaining = _len - (offset - start)
if remaining > 0:
    fields.append(_make_field("OD", offset, offset + remaining - 1,
                              data[offset:offset + remaining],
                              f"({remaining} bytes)", field_type="subrecord_data"))
```

**Тест:** отсутствует для SRT 34.

---

### Б-03. `_parse_srt_20` — тавтологические bounds checks

**Файл:** `gui/utils/byte_layout.py:816, 824`
**Функция:** `EGTS_SR_ACCEL_DATA` (профиль ускорения)

```python
# Строка 816:
if offset + 4 > offset + _len:
    return fields
atm = _uint32_le(data, offset)

# Строка 824:
for i in range(sa):
    if offset + 8 > offset + _len:
        break
```

`offset + 4 > offset + _len` упрощается до `4 > _len` — проверяет **не остаток буфера, а всю длину подзаписи**. То же для `8 > _len`. Поскольку `offset` инкрементально растёт при чтении, реальный остаток буфера может быть меньше `_len`, но проверка этого не учитывает.

**Последствия:**
- При `_len >= 8` цикл `for i in range(sa)` может выполнить `sa` итераций даже если данных не хватает.
- `_uint32_le(data, offset)` на строке 819 при `offset + 4 > len(data)` бросит `IndexError` (bytes slicing безопасен, но `int.from_bytes` тоже — но тут используется `_uint32_le` → `int.from_bytes(data[offset:offset+4], 'little')` — при `offset + 4 > len(data)` возвращает короткий int, не ошибку; **но дальнейший `int.from_bytes(data[offset:offset+2], 'little', signed=True)` на строке 831 вернёт некорректное значение**).

**Исправление:**
```python
if offset + 4 > len(data):
    return fields
atm = _uint32_le(data, offset)
# ...
for i in range(sa):
    if offset + 8 > len(data):  # ← было offset + _len
        break
```

**Тест:** отсутствует для SRT 20.

---

### Б-04. `compute_layout` — bounds check для записи APPDATA off-by-3

**Файл:** `gui/utils/byte_layout.py:1268`
**Функция:** цикл разбора записей в APPDATA

```python
# Строка 1268:
if rl_candidate == 0 or record_offset + 4 + rl_candidate > len(raw):
    break
```

Заголовок записи EGTS = 7 байт (RL:2 + RN:2 + RFL:1 + SST:1 + RST:1), не 4. Проверка `record_offset + 4 + rl_candidate` пропускает записи, у которых 3 последних байта заголовка выходят за буфер. `_build_record_layout` начнёт читать RFL/SST/RST по невалидным смещениям, что даст мусор или IndexError.

**Воспроизведение:** APPDATA-пакет, в котором последняя запись обрезана так, что RL+RN внутри буфера, а RFL/SST/RST — за пределами.

**Исправление:**
```python
if rl_candidate == 0 or record_offset + 7 + rl_candidate > len(raw):
    break
```

**Тест:** тест `test_full_packet_with_record` использует одну запись — не покрывает случай с обрезанной записью.

---

### Б-05. `_parse_srt_63` — секция точки трека всегда охватывает 2 байта

**Файл:** `gui/utils/byte_layout.py:1183`
**Функция:** `EGTS_SR_TRACK_DATA` (траекторные данные)

```python
# Строка 1183:
summary = f"Point {i + 1} [RTM={rtm * 0.1}s]"
fields.append(_make_section(
    f"Point {i + 1}",
    offset - 1 - len(data[offset-1:offset]),  # ← всегда offset - 2
    offset - 1,
    tp_fields,
    summary
))
```

`data[offset-1:offset]` — срез длиной 1 байт, `len(...)` = 1. Таким образом:
- начало секции = `offset - 1 - 1 = offset - 2`
- конец секции = `offset - 1`

Реальная точка трека может занимать до 13 байт (1 FLG + 4 LAT + 4 LONG + 3 SPD+DIRH + 1 DIR). При клике на «Point 1» в дереве **подсветка в hex viewer укажет только на 2 последних байта точки**, а не на всю точку.

**Исправление:**
```python
def _parse_srt_63(data, offset, _len):
    # ...
    for i in range(sa):
        point_start = offset  # ← сохранить
        # ... (FLG, опционально LAT/LONG/SPD, опционально DIR) ...
        fields.append(_make_section(
            f"Point {i + 1}",
            point_start,
            offset - 1,
            tp_fields,
            summary
        ))
```

**Тест:** отсутствует для SRT 63.

---

## 🟠 P0 — Пропуск функциональности

### Б-06. `_parse_srt_6` не читает ENA-поле (бит 0 AUTH_PARAMS FLG)

**Файл:** `gui/utils/byte_layout.py:679-738`
**Функция:** `EGTS_SR_AUTH_PARAMS` (параметры авторизации)

Согласно ГОСТ 33465-2015 (таблица 17), структура `EGTS_SR_AUTH_PARAMS`:
```
FLG(1) | [ENA(1)] | [PKL(2) + PK(PKL)] | [ISL(2) + IS(ISL)] | [MS(2)] | [SSL(2) + SS(SSL)] | [E(N)]
```

Код корректно обрабатывает флаги PKE (бит 1), ISLE (бит 2), MSE (бит 3), SSE (бит 4), EXE (бит 5), но **флаг ENA (бит 0) полностью проигнорирован** в условных переходах:

```python
# Строки 698-731 — обрабатывают только биты 1-5:
if _len >= 3 and (flg & 0x02):  # PKE
    ...
if _len >= 3 and (flg & 0x04):  # ISLE
    ...
# (нет обработки flg & 0x01)
```

Если сервер пришлёт пакет с `flg & 0x01` (ENA=1), то 1-байтное поле ENA будет пропущено, и все последующие поля сместятся на 1 байт → некорректный разбор.

**Воспроизведение:** AUTH_PARAMS с `flg = 0x01` или `flg = 0x03` (ENA+PKE) → PKL прочитается с позиции ENA, что даст мусор.

**Исправление:**
```python
# Вставить после чтения FLG, до PKL:
if flg & 0x01:  # ENA — Encryption Algorithm ID
    if pos + 1 <= len(data):
        ena_val = _int8(data, pos)
        fields.append(_make_field("ENA", pos, pos, data[pos:pos + 1], f"{ena_val}"))
        pos += 1
```

**Тест:** отсутствует для SRT 6.

---

## 🟡 P1 — Несогласованность offset_end и hex_display

### Б-07. Null-терминатор в offset_end vs hex_display

**Файлы:**
- `byte_layout.py:650-651` (SRN в MODULE_DATA)
- `byte_layout.py:656-657` (DSCR в MODULE_DATA)
- `byte_layout.py:735-736` (EXP в AUTH_PARAMS)
- `byte_layout.py:746-747, 751-752, 757-758` (UNM, UPSW, SS в AUTH_INFO)

**Паттерн:**
```python
srn, offset = _decode_until_null(data, offset)  # offset теперь ПОСЛЕ \x00
fields.append(_make_field(
    "SRN",
    offset - len(srn) - 1,           # начало строки (без \x00)
    offset - 2,                       # конец строки (без \x00)
    data[offset - len(srn) - 1:offset],  # срез ВКЛЮЧАЕТ \x00
    srn
))
```

`_decode_until_null` возвращает `offset = end_of_null + 1`. Тогда:
- `offset_end = offset - 2 = end_of_null - 1` → **строка без null-терминатора**
- `data[offset - len(srn) - 1 : offset] = data[start : end_of_null + 1]` → **включает null**

При клике в дереве поле подсвечивается без последнего байта, хотя в hex-колонке этот байт отображается.

**Исправление (вариант — унифицировать на «включая null»):**
```python
fields.append(_make_field(
    "SRN",
    offset - len(srn) - 1,
    offset - 1,                        # ← включая null-терминатор
    data[offset - len(srn) - 1:offset],
    srn
))
```

---

### Б-08. `live_packets.py:209-222` — дублирование логики «если уже открыто»

**Файл:** `gui/dashboard/cards/live_packets.py`

```python
# Блок 1 (с try/except):
if packet_id in self._open_detail_cards:
    try:
        card = self._open_detail_cards[packet_id]
        if card and not card.isHidden():
            card.raise_()
            return
    except:
        if packet_id in self._open_detail_cards:
            del self._open_detail_cards[packet_id]

# Блок 2 (без try/except) — делает то же самое:
if packet_id in self._open_detail_cards:
    self._open_detail_cards[packet_id].raise_()
    return
```

Второй блок **никогда не выполнится**, т.к. первый либо `return`-ит, либо удаляет из словаря. Либо первый блок бесполезен (если карта уже удалена Qt, она не должна быть в словаре).

**Исправление:**
```python
if packet_id in self._open_detail_cards:
    card = self._open_detail_cards.get(packet_id)
    if card is not None and not card.isHidden():
        card.raise_()
        return
    self._open_detail_cards.pop(packet_id, None)
```

---

### Б-09. Голый `except:` в `live_packets.py:215`

```python
except:
    if packet_id in self._open_detail_cards:
        del self._open_detail_cards[packet_id]
```

Ловит `KeyboardInterrupt`, `SystemExit`, всё. Заменить на `except (RuntimeError, ReferenceError):` — `isHidden()` может бросить `RuntimeError` для удалённого C++ объекта.

---

## 🟡 P1 — Мёртвый код

### Б-10. `_format_hex_dump` в `live_packets.py:297-308`

Метод определён, но нигде не вызывается (весь hex-дамп теперь через `HexDumpWidget`). Удалить или оставить как fallback для текстового экспорта.

---

### Б-11. Логика bounds check каскада в `_position_floating_card`

**Файл:** `live_packets.py:256-259`

```python
if x + 500 > main_geo.right():
    x = base_x
    y = base_y  # Reset cascade
```

При выходе за границу сбрасывается **и x, и y**, хотя комментарий говорит только про cascade offset. Логика неочевидна: если у нас 3 открытых карты, первая выйдет за границу, вторая/третья наложатся на первую.

**Исправление:** использовать модульную арифметику для каскада или сбрасывать только y, оставляя x с инкрементом.

---

## 🟢 P2 — Минорные замечания

### Б-12. Нет валидации FDL / HL в `compute_layout`

`fd l = _uint16_le(data, 5)` и `hl = _int8(data, 3)` читаются «as is». Если FDL > `len(raw) - hl`, то:
- `sfrd_data = raw[hl:hl + fdl]` корректно обрезается (строка 1294) ✓
- Но `sfrd_end = hl + fdl - 1` уходит за буфер → все циклы записей/подзаписей работают с «фантомными» данными.

Текущая защита только в CRC-секции (`if fdl <= len(raw) - hl`).

### Б-13. `_parse_srt_8` — `while pos + 2 < len(data)`

Корректно (читает 3 байта: ST, SST, SRVP), но неочевидно. Комментарий был бы полезен.

### Б-14. `_is_packet_ok` строит строку только ради bool

`gui/dashboard/cards/packet_detail.py:67-68`:
```python
def _is_packet_ok(self) -> bool:
    return not self._error_summary()
```

`_error_summary()` собирает список строк и join-ит их. Для bool-проверки достаточно вернуть сам список/первый элемент. Не критично, но лишняя работа.

### Б-15. `hex_viewer.py:160-163` — неэффективный `clear_highlight`

```python
def clear_highlight(self):
    self._hex_edit.setPlainText(self._hex_edit.toPlainText())
    self._ascii_edit.setPlainText(self._ascii_edit.toPlainText())
```

Перечитывает plain text и сбрасывает всё форматирование. Если в будущем добавится подсветка синтаксиса — она потеряется. Лучше хранить копию plain text в `set_hex_data`.

### Б-16. `compact_proxy` в `live_packets.py:67-76`

`CompactProxyModel` фильтрует «последние 5 строк», но исходная модель `PacketTableModel` хранит **все** пакеты. При длительной сессии память растёт линейно. Не баг, но потенциальная утечка.

---

## ✅ Что работает корректно

Проверено в коде и сопоставлено с ГОСТ 33465-2015:

| Компонент | Статус | Примечание |
|---|---|---|
| CRC-8 (HCS) | ✓ | Считается по `data[:hcs_offset]` (byte_layout.py:341) |
| CRC-16 (SFRCS) | ✓ | По `raw[hl:hl+fdl]`, корректно обрезается (1293-1295) |
| Флаги заголовка PRF/RTE/ENA/CMP/PR | ✓ | Битовая маска и порядок по Гост табл. 3 |
| PT (Packet Type) | ✓ | RESPONSE → идёт через `_build_response_sfrd` |
| PRA/RCA/TTL (при RTE=1) | ✓ | Условный парсинг корректен |
| RECORD_RESPONSE (SRT=0) | ✓ | CRN + RCS |
| TERM_IDENTITY (SRT=1) | ✓ | Порядок и длины полей по Гост табл. 16 |
| MODULE_DATA (SRT=2) | ✓ | Кроме ST=2..127 (отображается как int) |
| VEHICLE_DATA (SRT=3) | ✓ | Минимальная длина 25 проверяется |
| AUTH_INFO (SRT=7) | ✓ | UNM/UPSW/SS как null-terminated |
| SERVICE_INFO (SRT=8) | ✓ | Глобальный SRVP + цикл по сервисам |
| RESULT_CODE (SRT=9) | ✓ | |
| COMMAND_DATA (SRT=51) | ✓ | CT=5 (COM) и CT=1 (COMCONF) |
| RAW_MSD_DATA (SRT=62) | ⚠ | Bounds check отсутствует (Б-16 в foot_note) |
| Hex viewer подсветка | ✓ | `byte_to_pos` корректен для типичных пакетов |
| Compact/expanded view | ✓ | Базовая логика работает, `set_views` вызывается |
| Floating mode | ✓ | `WindowStaysOnTopHint` toggle, `WA_DeleteOnClose` |
| Tab «Protocol» | ✓ | Splitter tree ↔ hex viewer |
| Tab «Metadata» | ✓ | Timestamp, Channel, Direction, Length |

---

## 📋 План исправлений

| # | Файл | Строка | Действие | Приоритет |
|---|------|--------|----------|-----------|
| Б-01 | `gui/utils/byte_layout.py` | 876 | Сохранить `start = offset`, пересчитать `remaining` | P0 |
| Б-02 | `gui/utils/byte_layout.py` | 896 | То же для `_parse_srt_34` | P0 |
| Б-03 | `gui/utils/byte_layout.py` | 816, 824 | `> len(data)` вместо `> offset + _len` | P0 |
| Б-04 | `gui/utils/byte_layout.py` | 1268 | `+ 7 + rl` вместо `+ 4 + rl` | P0 |
| Б-05 | `gui/utils/byte_layout.py` | 1183 | Сохранять `point_start` для секции | P0 |
| Б-06 | `gui/utils/byte_layout.py` | 696 | Добавить `if flg & 0x01: read ENA` | P0 |
| Б-07 | `gui/utils/byte_layout.py` | 650, 656, 735, 746, 751, 757 | Унифицировать `offset_end` (включая null) | P1 |
| Б-08 | `gui/dashboard/cards/live_packets.py` | 209-222 | Убрать дублирующий блок | P1 |
| Б-09 | `gui/dashboard/cards/live_packets.py` | 215 | `except (RuntimeError, ReferenceError):` | P1 |
| Б-10 | `gui/dashboard/cards/live_packets.py` | 297-308 | Удалить `_format_hex_dump` | P2 |
| Б-11 | `gui/dashboard/cards/live_packets.py` | 256-259 | Пересмотреть логику каскада | P2 |
| Б-12 | `gui/utils/byte_layout.py` | 1216 | Валидация FDL/HL vs `len(raw)` | P2 |

---

## 🧪 Рекомендуемые тесты

Покрытие тестами нужно расширить:

1. `test_srt_33_full` — пакет SERVICE_PART_DATA с ODH+OD, проверить корректность OD-поля
2. `test_srt_34_full` — пакет SERVICE_FULL_DATA с ODH+OD (Б-02)
3. `test_srt_20_multi_measurement` — ACCEL_DATA с `sa=3`, проверить bounds (Б-03)
4. `test_srt_63_point_section_offsets` — TRACK_DATA с одной точкой, проверить offset_start/end (Б-05)
5. `test_srt_6_with_ena_flag` — AUTH_PARAMS с `flg=0x01` (ENA), проверить отсутствие смещения (Б-06)
6. `test_appdata_truncated_record` — запись, обрезанная посередине, проверить bounds check (Б-04)
7. `test_offset_end_includes_null` — для SRN/DSCR/UNM (Б-07)

---

## Заключение

Основная функциональность пакетного инспектора работает корректно для типичных сценариев (rx-пакеты, простые APPDATA с одной записью TERM_IDENTITY, RESPONSE). Однако **6 критических багов** в edge cases (SRT 33/34, ACCEL_DATA, TRACK_DATA, AUTH_PARAMS с ENA, обрезанные записи) могут приводить к:
- неверному отображению данных прошивки (OD-поле),
- IndexError или мусору в дереве при неполных пакетах,
- смещению полей в AUTH_PARAMS.

Рекомендуется **исправить все P0-баги одним PR** с добавлением соответствующих тестов, прежде чем продолжать расширение списка поддерживаемых подзаписей.
