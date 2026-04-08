# Changelog — OMEGA_EGTS

Все значимые изменения проекта. Формат: [Keep a Changelog](https://keepachangelog.com/), версионирование: [SemVer](https://semver.org/).

---

## [Unreleased]

### Этап 1: CLI MVP (в разработке)
- [x] EventBus — async шина с ordered/parallel handlers (итерация 1.1)
- [x] Config — nested dataclass'ы, JSON загрузка, CLI merge, валидация (итерация 1.2)
- [x] CoreEngine — координатор компонентов (итерация 1.3)
- [ ] FSM авторизации (TERM_IDENTITY → AUTH_PARAMS → AUTH_INFO → RESULT_CODE)
- [ ] asyncio TCP-сервер для приёма EGTS-пакетов
- [ ] Поддержка ГОСТ 33465-2015 (транспортный уровень)
- [ ] Эмулятор CMW-500 для тестирования
- [ ] CLI (REPL на cmd)
- [ ] Базовое логирование пакетов (hex + parsed)
- [ ] pytest, покрытие ≥ 90%

### Этап 2: Библиотека EGTS (в разработке)
- [x] egts_protocol_iface — IEgtsProtocol (Protocol), create_protocol factory (итерация 2.1–2.2)
- [x] Модели: Packet, Record, Subrecord, ParseResult (dataclass-контракты с extra, parse_error, crc_valid)
- [x] Enums: PacketType, ServiceType, SubrecordType, RecordStatus, ResultCode + константы
- [x] Методы сборки: pr_flags(), rf_flags() для флагов PR/RF
- [x] Заглушка egts_protocol_gost2015/adapter.py (EgtsProtocol2015)
- [x] EgtsProtocol2015 — парсинг/сборка пакетов (итерация 2.3)
  - Полная реализация parse_packet, build_response, build_record_response, build_packet
  - Чистая реализация CRC-8/CRC-16 на Python (без crcmod)
  - Маппинг между internal-моделями (EGTS_GUI) и iface-моделями
  - 27 новых тестов адаптера
- [ ] SMS PDU — полная интеграция в адаптере (итерация 2.4, параллельный агент)

### Этап 3: Сценарии (планируется)
- [ ] Все 10 сценариев (авторизация, телеметрия, траектория, ускорение, eCall, обновление ПО, команды, тестирование, SMS, пассивный режим)
- [ ] Загрузка/генерация HEX-файлов
- [ ] Export (CSV/JSON/DER)
- [ ] CredentialsRepository (JSON-хранилище)

### Этап 4: ГОСТ 2023 (планируется)
- [ ] Поддержка ГОСТ 33465-2023

### Этап 5: GUI (планируется)
- [ ] Графический интерфейс оператора (PyQt6/PySide6)

### Этап 6: Реальное CMW-500 (планируется)
- [ ] Интеграция с реальным оборудованием CMW-500 (PyVISA/SCPI)

---

## [0.0.0] — 2026-04-06

### Инициализация проекта
- Создание структуры проекта
- Техническое задание (`docs/ТЗ_тестер_УСВ.md`)
- Текст ГОСТ 33465-2015 (`docs/gost.md`)
- Тестовые данные (`docs/*.xlsx`)
- Навык `gost-compliance` для проверки соответствия ГОСТ
- Конвенции разработки и архитектурные принципы

[Unreleased]: https://github.com/your-org/OMEGA_EGTS/compare/v0.0.0...HEAD
