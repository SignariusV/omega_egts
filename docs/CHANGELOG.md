# Changelog

Все значимые изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).

## [Unreleased]

### Added
- **AuthValidationMiddleware**: валидация TERM_IDENTITY и VEHICLE_DATA против конфигурации (ТЗ п. 2.3.1 шаг 8, 10)
- **ServiceInfoValidator**: проверка сервисов — только ST=10 (EGTS_ECALL_SERVICE) разрешён (ТЗ п. 2.3.1 шаг 11)
- **Форматная валидация** IMEI/IMSI/MSISDN в `Credentials` (ТЗ п. 2.1.3)
- **AuthValidator**: сверка параметров авторизации (IMSI, IMEI, MSISDN, UNIT_ID) и аутентификации (VIN, категория ТС, тип топлива)
- **События EventBus**: `auth.validation_passed`, `auth.validation_failed`, `service_info.requested`, `service_info.responded`
- ~40 кодов команд в `COMMAND_CODES` из таблиц 32, 34, 46, 47 ГОСТ 33465-2015
- 28 тестов round-trip для всех 14 парсеров subrecord

### Changed
- `CmwConfig.mnc` исправлен с 60 на 77 (ТЗ: NID=25077)
- `docs/ARCHITECTURE.md`: добавлены секции подзаписей и кодов команд

### Fixed
- `TestServicePartDataRoundtrip`: корректная обработка null-терминатора ODH

## [0.1.0] — 2026-05-15

### Added
- Базовая структура ядра: CoreEngine, EventBus, SessionManager, FSM
- EGTS библиотека: парсер/билдер, CRC-8/16, реестр протоколов
- Pipeline: 5 middleware (CRC, Parse, Dedup, AutoResponse, EventEmit)
- CMW-500 контроллер: SCPI-команды, эмулятор
- TCP-сервер: asyncio, управление сессиями
- Сценарии: парсер V1, StepFactory, ExpectStep, SendStep
- Логирование: JSONL, daily rotation
- CLI: команды start, status, run-scenario, replay, export
