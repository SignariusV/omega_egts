# Аутентификация

## Описание
Процедура аутентификации УСВ по TCP/IP согласно ГОСТ 6.7.2.

## Схема обмена

```
┌──────────┐                                    ┌─────┐
│ПЛАТФОРМА │                                    │ УСВ │
└────┬─────┘                                    └──┬──┘
     │ 1. TERM_IDENTITY → идентификация (TID, IMEI, IMSI)
     │ 2. RESPONSE      ← подтверждение (RPID=PID)
     │ 3. VEHICLE_DATA  → данные ТС (VIN, тип, цвет)
     │ 4. RESPONSE      ← подтверждение (RPID=PID)
     │ 5. RESULT_CODE   ← результат (EGTS_PC_OK=0)
     │ 6. RESPONSE      → подтверждение результата
     │                                            │
     │  ✅ УСВ авторизован                        │
```

## Шаги

| # | Пакет | Направление | Размер | Описание |
|---|-------|-------------|--------|----------|
| 1 | EGTS_SR_TERM_IDENTITY | УСВ → Платформа | 59 байт | TID=1, IMEI, IMSI |
| 2 | EGTS_SR_RECORD_RESPONSE | Платформа → УСВ | 29 байт | Подтверждение TERM_IDENTITY |
| 3 | EGTS_SR_VEHICLE_DATA | УСВ → Платформа | 48 байт | VIN, тип ТС, энергоноситель |
| 4 | EGTS_SR_RECORD_RESPONSE | Платформа → УСВ | 29 байт | Подтверждение VEHICLE_DATA |
| 5 | EGTS_SR_RESULT_CODE | Платформа → УСВ | 24 байт | Результат (EGTS_PC_OK=0) |
| 6 | EGTS_SR_RECORD_RESPONSE | УСВ → Платформа | 29 байт | Подтверждение результата |

## FSM переходы

`CONNECTED` → `AUTHENTICATING` → `AUTHORIZED`

## Пакеты

- `packets/usv/term_identity.hex` — идентификация терминала
- `packets/usv/vehicle_data.hex` — данные ТС
- `packets/platform/record_response_*.hex` — подтверждения
- `packets/platform/result_code.hex` — результат аутентификации
- `packets/usv/record_response_result.hex` — подтверждение результата
