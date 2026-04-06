# Сценарии тестирования УСВ

## Структура

```
scenarios/
├── verification/       # Верификация (SMS) — 6 пакетов
├── auth/               # Аутентификация (TCP/IP) — 6 пакетов
├── track/              # Передача траектории — 4 пакета
├── accel/              # Передача профиля ускорения — 4 пакета
├── fw_update/          # Обновление ПО — 4 пакета
├── commands/           # Команды конфигурирования — 3 пакета
├── ecall/              # Экстренный вызов (заглушка)
├── telemetry/          # Телеметрия (заглушка)
├── passive_mode/       # Пассивный режим
└── test_mode/          # Режим тестирования
```

## Основные сценарии (из тестов)

| # | Сценарий | Папка | Каналы | Пакетов | Описание |
|---|----------|-------|--------|---------|----------|
| 1 | Первичная настройка | verification + auth | SMS + TCP/IP | 12 | Верификация + Аутентификация |
| 2 | Передача траектории | track | SMS + TCP/IP | 4 | SMS-запрос → данные |
| 3 | Передача ускорения | accel | SMS +TCP/IP | 4 | SMS-запрос → данные |
| 4 | Обновление ПО | fw_update | TCP/IP | 4 | Прошивка (2 части, 80 КБ) |
| 5 | Команды конфигурирования | commands | TCP/IP | 3 | Команда → ответ → подтверждение |

## Формат scenario.json

```json
{
  "name": "Название сценария",
  "version": "2015",
  "timeout": 30,
  "description": "Описание сценария",
  "channels": ["tcp", "sms"],
  "steps": [
    {
      "name": "Название шага",
      "type": "expect|send|verify",
      "channel": "tcp|sms",
      "direction": "from_usv|from_platform",
      "packet_type": "EGTS_SR_TERM_IDENTITY",
      "packet_file": "packets/usv/term_identity.hex",
      "timeout": 6,
      "capture": {"var_name": "field_path"},
      "checks": {"field": "expected_value"},
      "description": "Описание шага"
    }
  ]
}
```

### Типы шагов

| Тип | Описание |
|-----|----------|
| `expect` | Ожидание пакета от УСВ |
| `send` | Отправка пакета на УСВ |
| `verify` | Проверка условия (без отправки/ожидания) |

### Поля шага

| Поле | Обязательность | Описание |
|------|----------------|----------|
| `name` | ✅ | Название шага |
| `type` | ✅ | Тип действия |
| `channel` | ✅ | Канал связи |
| `direction` | ✅ | Направление |
| `packet_type` | ✅ | Тип пакета |
| `packet_file` | Для `send` | Путь к HEX-файлу |
| `timeout` | ✅ | Таймаут (сек) |
| `capture` | ⬜ | Захват переменных |
| `checks` | ⬜ | Проверки полей |
| `description` | ✅ | Описание |

## Пакеты

Каждый сценарий содержит HEX-файлы в `packets/`:

```
scenarios/<name>/
├── scenario.json
├── README.md
└── packets/
    ├── platform/   # Пакеты от Платформы
    └── usv/        # Пакеты от УСВ
```

## Запуск сценария

```bash
# Запуск сценария
egts-tester run-scenario scenarios/auth/

# Запуск с таймаутом
egts-tester run-scenario scenarios/track/ --timeout 60

# Запуск в пассивном режиме (только приём)
egts-tester run-scenario scenarios/auth/ --passive
```
