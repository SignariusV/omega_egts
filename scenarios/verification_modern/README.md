# Верификация (SMS) — modern (Phase 1-2-3)

## Описание
Первоначальная настройка УСВ через SMS-канал с динамической генерацией пакетов,
`{{var}}` подстановкой в checks и capture sent-значений (cid/sid).

## Схема обмена

```
┌──────────┐      SMS-КАНАЛ           ┌─────┐
│ПЛАТФОРМА │                          │ УСВ │
└────┬─────┘                          └──┬──┘
     │ 1. GPRS_APN     → build CMD_DATA  │
     │ 2. COMCONF      ← check {{sent_cid}}/{{sent_sid}}/{{record_id}}
     │ 3. SERVER_ADDR  → build CMD_DATA  │
     │ 4. COMCONF      ← check {{sent_cid}}/{{sent_sid}}/{{record_id}}
     │ 5. UNIT_ID      → build CMD_DATA  │
     │ 6. COMCONF      ← check + capture │
     │                                  │
     │  ✅ Верификация ({{var}} checks) │
```

## Шаги

| # | Пакет | Направление | Тип | Описание |
|---|-------|-------------|-----|----------|
| 1 | EGTS_GPRS_APN | Платформа → УСВ | send | build {{packet_id}}/{{record_id}}, APN=internet |
| 2 | CT_COMCONF | УСВ → Платформа | expect | check {{sent_cid}}/{{sent_sid}}/{{record_id}} |
| 3 | EGTS_SERVER_ADDRESS | Платформа → УСВ | send | build {{packet_id}}/{{record_id}}, адрес сервера |
| 4 | CT_COMCONF | УСВ → Платформа | expect | check {{sent_cid}}/{{sent_sid}}/{{record_id}} |
| 5 | EGTS_UNIT_ID | Платформа → УСВ | send | build {{packet_id}}/{{record_id}}, UNIT_ID |
| 6 | CT_COMCONF | УСВ → Платформа | expect | check + capture unit_id |

## Variables

- `packet_id` — автоинкремент (start=27)
- `record_id` — автоинкремент (start=42)
- `service_type` — статическая (4)
- `recipient_service_type` — статическая (4)
- `unit_id_hex` — статическая ("00000001")
- `gprs_apn_dt` — статическая ("internet")
- `server_address_dt` — resolver `server_address`

## Особенности

- **Phase 1**: проверка `subrecord_type: 51` как int (не строка)
- **Phase 2**: подстановка `{{packet_id}}`, `{{record_id}}`, `{{gprs_apn_dt}}` в build-шаблоны
- **Phase 3**: проверка `cid: "{{sent_cid}}"`, `sid: "{{sent_sid}}"` — захват из отправленных SendStep
- **record_id в checks**: каждый ExpectStep проверяет `record_id: "{{record_id}}"` (дополнительная валидация)
- **Resolver**: адрес сервера подставляется через resolver, не хардкодом
