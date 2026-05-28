# Аутентификация TCP — modern (Phase 1-2-3)

## Описание
Аутентификация УСВ с динамической генерацией пакетов, `{{var}}` подстановкой в checks,
resolvers для IMEI/IMSI и capture структурных полей (record_id, response_packet_id).

## Схема обмена

```
┌──────────┐                                    ┌─────┐
│ПЛАТФОРМА │                                    │ УСВ │
└────┬─────┘                                    └──┬──┘
     │ 1. TERM_IDENTITY → идентификация (TID, IMEI, IMSI)
     │ 2. RESPONSE      ← build {{pid}}/{{rn}}   │
     │ 3. RECORD_RESPONSE → extra: response_packet_id, record_id
     │ 4. VEHICLE_DATA  → данные ТС (VIN, тип)   │
     │ 5. RESPONSE      ← build {{pid}}/{{rn}}   │
     │ 6. RECORD_RESPONSE → check {{sent_pid}}   │
     │ 7. RESULT_CODE   ← build RCD=0            │
     │ 8. RECORD_RESPONSE → check {{sent_pid}}   │
     │                                            │
     │  ✅ УСВ авторизован (динамические PID/RN)  │
```

## Шаги

| # | Пакет | Направление | Тип | Описание |
|---|-------|-------------|-----|----------|
| 1 | EGTS_SR_TERM_IDENTITY | УСВ → Платформа | expect | TID, IMEI, IMSI — захват data |
| 2 | EGTS_PT_RESPONSE | Платформа → УСВ | send | build {{pid}}/{{rn}}, CRN=1, RST=0 |
| 3 | EGTS_SR_RECORD_RESPONSE | УСВ → Платформа | expect | check subrecord_type=0, capture response_packet_id |
| 4 | EGTS_SR_VEHICLE_DATA | УСВ → Платформа | expect | VIN, VHT, VPST — захват record_id |
| 5 | EGTS_PT_RESPONSE | Платформа → УСВ | send | build {{pid}}/{{rn}}, CRN=2, RST=0 |
| 6 | EGTS_SR_RECORD_RESPONSE | УСВ → Платформа | expect | check {{sent_pid}} (Phase 3) |
| 7 | EGTS_SR_RESULT_CODE | Платформа → УСВ | send | build RCD=0 |
| 8 | EGTS_SR_RECORD_RESPONSE | УСВ → Платформа | expect | check {{sent_pid}} + record_status |

## Variables

- `pid` — автоинкремент (start=1), для packet_id отправляемых пакетов
- `rn` — автоинкремент (start=1), для record_id отправляемых пакетов
- `imei_default` — resolver `imei` (берётся из настроек)
- `imsi_default` — resolver `imsi`
- `command_sid` — статическая переменная (2)

## Особенности

- **Phase 1**: проверка `subrecord_type` как int, capture `record_id`/`response_packet_id` из extra
- **Phase 2**: подстановка `{{pid}}`, `{{rn}}` в build-шаблоны
- **Phase 3**: проверка `response_packet_id: "{{sent_pid}}"` — захват sent_pid из предыдущего SendStep
- **Resolvers**: IMEI и IMSI подставляются через resolver, а не хардкодом
