# План: Интеграция статуса CMW-500 в EventBus

## Цель

Получить данные от CMW-500 (IMEI, IMSI, RSSI, состояние соединения) и передавать в GUI/другие компоненты через EventBus.

## Контекст

- Методы `get_imei()`, `get_imsi()` уже существуют в `Cmw500Controller` (строки 497-505), но **не используются**
- Метод `get_full_status()` уже существует и возвращает ВСЕ текущие параметры
- Задача: интегрировать в архитектуру через EventBus, **максимально используя существующий код**

---

## Что делаем (минимальные изменения)

### Этап 1: Добавить событие `cmw.status` (ОСНОВНОЕ)

**Использовать существующий метод:** `get_full_status()`

Этот метод уже возвращает:
- `cs_state`, `ps_state`, `rssi`, `rssi_range`, `cell_status`, `ber`, `rx_level`

**Нужно_extensions:** добавить `imei`, `imsi` в `get_full_status()`

| Что менять | Файл | Изменение |
|------------|------|-----------|
| `VisaCmw500Driver.get_imei()` | `cmw500.py:133` | Уже есть |
| `VisaCmw500Driver.get_imsi()` | `cmw500.py:138` | Уже есть |
| `get_full_status()` | `cmw500.py:545` | Добавить imei/imsi |

**Реализация:**

1. В `_poll_loop()` добавить вызов `get_full_status()` и emit:
   ```python
   async def _poll_loop(self) -> None:
       while self._connected:
           try:
               await self._poll_incoming_sms()
               # НОВОЕ: emit cmw.status
               status = await self.get_full_status()
               await self.bus.emit("cmw.status", status)
           except Exception as e:
               await self.bus.emit("cmw.error", ...)
           await asyncio.sleep(self._poll_interval)
   ```

2. Расширить `get_full_status()` — добавить imei/imsi в возвращаемый dict:
   ```python
   # В get_full_status() после сбора данных:
   result = {
       "connected": True,
       "serial": serial,
       "cs_state": cs_state,
       "ps_state": ps_state,
       "rssi": rssi,
       # ... остальные поля
       "imei": await self.get_imei(),    # НОВОЕ
       "imsi": await self.get_imsi(),     # НОВОЕ
   }
   ```

**Периодичность:** Использовать существующий `_poll_interval` (2 секунды)

---

### Этап 2: Обновить документацию (минимально)

**Файл:** `docs/ARCHITECTURE.md`

Добавить одну строку в таблицу событий:

| Событие | Данные | Кто публикует | Кто подписывается |
|---------|--------|---------------|-------------------|
| `cmw.status` | cs_state, ps_state, rssi, ber, rx_level, cell_status, imei, imsi, timestamp | Cmw500Controller | GUI |

---

## Файлы для изменения (МИНИМАЛЬНО)

| Файл | Что менять | Объём |
|------|-----------|-------|
| `core/cmw500.py` | 1. Расширить `get_full_status()` 2. Добавить emit в `_poll_loop()` | ~10 строк |
| `docs/ARCHITECTURE.md` | Добавить событие в таблицу | ~5 строк |

---

## Особенности реализации

### Обработка ошибок

- Если `get_imei()`/`get_imsi()` не работает (УСВ не подкл��чено к CMW) → вернуть `None`
- Не блокировать emit `cmw.status` — просто пропустить если ошибка

### Интервал

Использовать существующий `_poll_interval` (2 секунды). Не добавлять новых параметров.

### Логирование

**НЕ логировать** `cmw.status` в LogManager (слишком часто). Только для GUI.

---

## Пример payload `cmw.status`

```python
{
    "connected": True,
    "serial": "EMULATOR",
    "cs_state": "SYNC",
    "ps_state": "ATT",
    "rssi": "-65",
    "rssi_range": "INV,INV",
    "cell_status": "ON,ADJ",
    "ber": 0.001,
    "rx_level": -70.0,
    "imei": "351234567890123",    # из get_imei()
    "imsi": "250011234567890",  # из get_imsi()
    "simulate": True,
    "ip": "192.168.2.2",
    "timestamp": 1714300000.123   # НОВОЕ (опционально)
}
```

---

## Почему так (обоснование)

1. **Минимум изменений** — используем `get_full_status()` который уже есть
2. **Одно событие** — проще подписываться, консистентные данные
3. **Периодический emit** — GUI получает обновления автоматически
4. **Расширение, не переписывание** — добавляем imei/imsi в существующий метод

---

## Расширяемость

**Вариант:** А — просто добавлять поля по необходимости

Добавлять новые поля в `get_full_status()` и `cmw.status` по мере необходимости.
GUI игнорирует неизвестные поля автоматически.

Пример:
- v1.0: imei, imsi, rssi, cs_state, ps_state
- v1.1: +mcc, +mnc (просто добавить в dict)

**Документировать:** новое поле → добавить в таблицу ARCHITECTURE.md

---

## Статус

- [ ] Этап 1: Добавить `cmw.status` (используя get_full_status)
- [ ] Этап 2: Обновить документацию

**Created:** 2026-04-28
**Updated:** 2026-04-28 (переработано с учётом минимизации изменений)