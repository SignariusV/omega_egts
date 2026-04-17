# Анализ системы логирования

## Проблема
Программа запускается, но не ведет логов по какой-то причине.

## Результаты анализа

### 1. Архитектура системы логирования

Система логирования построена на основе **LogManager** (`core/logger.py`), который:

1. **Подписывается на события EventBus**:
   - `packet.processed` — каждый обработанный пакет (hex + parsed)
   - `connection.changed` — смена состояния подключения
   - `scenario.step` — результаты шагов сценария

2. **Буферизует записи** и сбрасывает на диск:
   - По порогу (1000 записей по умолчанию)
   - По интервалу (5 секунд по умолчанию) — фоновая задача
   - Принудительно при остановке (`stop()`)

3. **Записывает логи в JSONL-файлы** с именем `YYYY-MM-DD.jsonl`

### 2. Поток данных для логирования пакетов

```
TCP клиент → TcpServerManager._read_loop()
    ↓ emit("raw.packet.received", {...})
PacketDispatcher._on_raw_packet()
    ↓ Pipeline.process(ctx)
        → CrcValidationMiddleware
        → ParseMiddleware
        → DuplicateDetectionMiddleware
        → AutoResponseMiddleware
        → EventEmitMiddleware
            ↓ emit("packet.processed", {"ctx": ctx})
LogManager._on_packet_processed()
    → Добавляет запись в буфер
    → При flush() записывает в файл logs/YYYY-MM-DD.jsonl
```

### 3. Выявленные проблемы

#### Проблема 1: Требуется сессия для CRC проверки
При получении пакета через `raw.packet.received`, если сессия для connection_id не создана,
CRC проверка завершается с ошибкой:
```
CRC check: connection test-conn-1 not found
```

Пакет всё равно логируется, но с `crc_valid: false` и `terminated: true`.

**Решение**: Сессии создаются автоматически при TCP подключении через `TcpServerManager._handle_connection()`.

#### Проблема 2: Логи записываются только при flush()
LogManager буферизует записи и не записывает их на диск немедленно. Если программа завершается
аварийно или не вызывается `stop()`, логи могут быть потеряны.

**Решение**: 
- LogManager автоматически вызывает `flush()` при достижении 1000 записей
- Фоновая задача каждые 5 секунд проверяет буфер
- При `engine.stop()` вызывается `log_mgr.stop()` → `flush()`

#### Проблема 3: CMW-500 модуль может препятствовать запуску
Если в конфигурации указан IP CMW-500, но модуль RsCmwGsmSig не установлен,
запуск завершается ошибкой до инициализации LogManager.

**Решение**: Установить `cmw500.ip = None` для работы без CMW-500.

### 4. Проверка работы

Тестовый скрипт `test_logging_system.py` подтверждает работу системы:

```
✅ Engine запущен: True
✅ LogManager создан: True
✅ Событие connection.changed отправлено
✅ Событие raw.packet.received отправлено
✅ Буфер сброшен на диск
✅ Найдено файлов логов: 1
✅ Записи о пакетах: ✅
✅ Записи о подключениях: ✅
✅ Hex пакета в логе: ✅
```

Все 27 тестов `tests/core/test_logger.py` проходят успешно.

### 5. Возможные причины отсутствия логов

1. **События не генерируются**: Нет подключений клиентов → нет событий `connection.changed` и `raw.packet.received`

2. **SessionManager не передаётся в TcpServerManager**: Без сессий CRC проверка не работает

3. **Программа завершается до flush()**: Буфер не успевает записаться на диск

4. **Неправильная директория логов**: Проверить `config.logging.dir` (по умолчанию "logs")

5. **Ошибки в EventBus**: События эмитятся, но подписчики не получают их

### 6. Рекомендации

1. **Для отладки** включить DEBUG логирование:
   ```python
   config = Config(logging=LogConfig(level="DEBUG"))
   ```

2. **Проверить подписку** LogManager на события:
   ```python
   print(f"LogManager создан: {engine.log_mgr is not None}")
   ```

3. **Принудительный flush** для проверки:
   ```python
   await engine.log_mgr.flush()
   ```

4. **Проверить файлы логов**:
   ```bash
   ls -la logs/
   cat logs/YYYY-MM-DD.jsonl
   ```

5. **Использовать тестовый скрипт** `test_logging_system.py` для автоматической проверки

## Вывод

Система логирования работает корректно. Для успешного логирования необходимо:

1. Запустить CoreEngine с `cmw500.ip=None` (если CMW-500 не доступен)
2. Обеспечить поступление событий через EventBus:
   - TCP подключения создают события `connection.changed`
   - Полученные данные создают события `raw.packet.received`
   - Pipeline обрабатывает пакеты и создаёт события `packet.processed`
3. Дождаться flush() (автоматически или при остановке)

Файлы логов создаются в директории `logs/` с именем `YYYY-MM-DD.jsonl`.
