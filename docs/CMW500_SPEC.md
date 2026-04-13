

# CMW-500: Спецификация и план реализации

> Документ для проектирования интеграции с Rohde & Schwarz CMW-500.
> Все состояния, команды, режимы и план — в одном месте.

---

## 1. Подключение к прибору

### 1.1 Библиотеки Rohde & Schwarz

**Две отдельные библиотеки — разные задачи:**

| Библиотека | Назначение | pip | Когда используем |
|------------|-----------|-----|-----------------|
| **`RsCmwGsmSig`** | GSM **Signaling** — управление соединениями, SMS, состояниями каналов | `pip install RsCmwGsmSig` | ✅ **Основная** — подключение УСВ, SMS, CS/PS состояния |
| **`RsCmwGsmMeas`** | GSM **Measurements** — анализ радиосигнала (EVM, BER, мощность) | `pip install RsCmwGsmMeas` | ❌ Не нужна — мы не измеряем PHY-уровень |

**RsCmwGsmSig** — наш выбор. Управляет:
- Установкой/разрывом CS и PS соединений
- Отправкой/приёмом SMS
- Конфигурацией ячейки (MCC/MNC/RF)
- Чтением состояний соединений (Sense)

**RsCmwGsmMeas** — НЕ нужна для нашего проекта. Она измеряет:
- EVM (Error Vector Magnitude)
- BER на уровне физического сигнала
- Мощность во времени (PowerVsTime)
- Модуляцию, IQ-констелляции
- Это уровень PHY — мы работаем на уровне протокола (signaling)

Обе тянут `RsCmwBase` как базовую зависимость.

### 1.2 Транспортные интерфейсы

| Интерфейс | VISA Resource String | Описание |
|-----------|---------------------|----------|
| LAN (VXI-11) | `TCPIP::<IP>::INSTR` | Стандартное LAN-подключение |
| LAN HiSLIP | `TCPIP::<IP>::hislip0` | Высокоскоростное LAN (рекомендуется) |
| GPIB | `GPIB::<ADDR>::INSTR` | GPIB-подключение (адрес 0-30) |
| USB-TMC | `USB::<VID>::<PID>::<SERIAL>::INSTR` | USB Test & Measurement Class |
| Raw Socket | `TCPIP::<IP>::<PORT>::SOCKET` | Прямой TCP-сокет (порт обычно 5025) |

**Наш случай:** LAN HiSLIP — `TCPIP::192.168.1.100::hislip0`

### 1.2 Библиотека

```
pip install RsCmwGsmSig    # тянет RsCmwBase как зависимость
```

- Инициализация: `RsCmwGsmSig(resource, id_query=True, reset=False)`
- `id_query=True` — проверяет совместимость модели при подключении
- `reset=False` — НЕ сбрасывать прибор (мы настраиваем вручную)

### 1.3 Утилиты

```python
driver.utilities.visa_timeout = 5000               # мс
driver.utilities.instrument_status_checking = True  # автопроверка ошибок
driver.utilities.opc_query_after_write = False      # авто-OPC после записи
driver.utilities.query_str('*IDN?')                 # идентификация
driver.utilities.write_str('*RST')                  # сброс
driver.utilities.query_opc()                        # ждать завершения команд
```

### 1.4 Идентификация сессии

| Свойство | Пример | Зачем |
|----------|--------|-------|
| `instrument_serial_number` | `100001` | **Основной ID** — уникален для прибора |
| `idn_string` | `Rohde&Schwarz,CMW500,100001,3.7.30.0023` | Полная идентификация |
| `get_session_handle()` | Строка-хендл | Уникален на каждую инициализацию |
| `resource_name` | `TCPIP::192.168.1.100::HISLIP` | Наш адрес подключения |

**Используем:** `instrument_serial_number` — включаем в события `cmw.connected`, `cmw.disconnected`, логи.

---

## 2. Состояния GSM Signaling

### 2.1 Состояния CS-канала (Circuit Switched)

**SCPI:** `FETCh:GSM:SIGN:CSWitched:STATe?`
**API:** `driver.utilities.query_str_with_opc('FETCh:GSM:SIGN:CSWitched:STATe?')`

⚠️ **Важно:** Использовать `query_str_with_opc()` вместо `query_str()` — команда ждёт завершения операции (`*OPC`) перед чтением ответа. `CALL:` команда не работает на этом приборе.

| Состояние | Значение | Описание |
|-----------|----------|----------|
| `DISConnect` | Нет соединения | Терминал не зарегистрирован |
| `PREParation` | Подготовка | Идёт установка соединения |
| `CONNected` | Подключён | CS-канал установлен, ожидание действий |
| `ACTive` | Активен | Идёт вызов / передача данных |
| `HOLD` | Удержание | Выов поставлен на удержание |
| `REL ease` | Освобождение | Завершение соединения |

### 2.2 Состояния PS-канала (Packet Switched)

**SCPI:** `FETCh:GSM:SIGN:PSWitched:STATe?`
**API:** `driver.utilities.query_str_with_opc('FETCh:GSM:SIGN:PSWitched:STATe?')`

⚠️ **Важно:** Использовать `query_str_with_opc()` вместо `query_str()`.

| Состояние | Значение | Описание |
|-----------|----------|----------|
| `DISConnect` | Нет соединения | PS-канал не установлен |
| `PREParation` | Подготовка | Идёт установка PDP-контекста |
| `CONNected` | Подключён | PS-канал готов к передаче данных |
| `ACTive` | Активен | Идёт передача данных |

### 2.3 Состояние Handover

**SCPI:** `CALL:GSM:SIGN:HANDover:STATe?`
**API:** `driver.call.handover.state.get()`

| Состояние | Значение | Описание |
|-----------|----------|----------|
| `IDLE` | Не активен | Хэндовер не выполняется |
| `PREParation` | Подготовка | Подготовка к хэндоверу |
| `ACTive` | Активен | Процедура хэндовера выполняется |
| `COMPLetion` | Завершение | Хэндовер завершён |

### 2.4 Статус CS-соединения (Sense)

**SCPI:** `SENSe:CONNection:CSWitched:CONNection?`
**API:** `driver.sense.connection.cswitched.connection.get()`

| Значение | Описание |
|----------|----------|
| `DISConnect` | Соединение отсутствует |
| `PREPare` | Подготовка к соединению |
| `CONNected` | Соединение установлено |
| `ACTive` | Активная передача |
| `REL ease` | Завершение |

### 2.5 Текущее состояние прибора (CONN?)

**SCPI:** `CMW:GSM:SIGN:CONN?` (сокращённая команда)
**API:** — (низкоуровневая команда, не из RsCmwGsmSig)

Возвращает числовой или текстовый статус. В нашем эмуляторе: `"1"` = подключён.
В ТЗ ожидается отображение: `registered` / `disconnected`.

---

## 3. Режимы работы CMW-500 в нашем проекте

### 3.1 Режим 1: TCP-сервер через WiFi CMW-500

- CMW-500 создаёт WiFi-сеть, УСВ подключается к ней
- CMW-500 проксирует TCP-соединение между УСВ и нашим сервером
- **Мы:** запускаем `TcpServerManager`, принимаем EGTS-пакеты
- **CMW-500:** не требует SCPI-команд для этого режима (только начальная настройка)

### 3.2 Режим 2: SMS-канал через LAN/SCPI

- Мы отправляем SCPI-команды CMW-500 для отправки SMS на УСВ
- CMW-500 опрашивается на наличие входящих SMS от УСВ
- **Мы:** `Cmw500Controller.send_sms()`, `read_sms()`, poll-loop

### 3.3 Режим 3: Голосовой канал eCall (будущее)

- CMW-500 эмулирует тональный модем для передачи MSD по голосовому каналу
- Требует активации CS-вызова и специального режима
- **Статус:** не реализовано, Этап 6

---

## 4. SCPI-команды

### 4.1 Реализованные (чтение)

| Метод | SCPI | API RsCmwGsmSig | Возвращает | Покрытие |
|-------|------|-----------------|------------|----------|
| `get_imei()` | `CMW:GSM:SIGN:IMEI?` | — | IMEI строка | ✅ |
| `get_imsi()` | `CMW:GSM:SIGN:IMSI?` | — | IMSI строка | ✅ |
| `get_rssi()` | `CMW:GSM:SIGN:RSSI?` | — | RSSI (dBm) | ✅ |
| `get_status()` | `CMW:GSM:SIGN:CONN?` | — | статус (строка) | ✅ |
| `read_sms()` | `CMW:GSM:SIGN:SMS:READ?` | `sense.sms.incoming.info` | HEX-данные SMS | ✅ |

### 4.2 Реализованные (запись)

| Метод | SCPI | API RsCmwGsmSig | Параметры |
|-------|------|-----------------|-----------|
| `send_sms()` | `CMW:GSM:SIGN:SMS:SEND {hex}` | `configure.sms.outgoing` | HEX-байты EGTS |

### 4.3 НЕРЕАЛИЗОВАННЫЕ — конфигурация GSM (из docs/comands.txt)

| Параметр | SCPI | API RsCmwGsmSig | Значение | Зачем |
|----------|------|-----------------|----------|-------|
| MCC | `CONF:GSM:SIGN:CELL:MCC` | `configure.cell.ncc` (или через MCC) | `250` | Код страны |
| MNC | `CONF:GSM:SIGN:CELL:MNC` | `configure.cell.mnc.set()` | `60` или `01` | Код оператора |
| RF Level TCH | `CONF:GSM:SIGN:RFSettings:LEVel:TCH` | `configure.rf_settings.level.tch.set()` | `-40` dBm | Мощность сигнала |
| PS Service | `CONF:GSM:SIGN:CONN:PSW:SERVice` | `configure.connection.pswitched.service.set()` | `TMA` | Тип PS-сервиса |
| PS TLevel | `CONF:GSM:SIGN:CONN:PSW:TLEVel` | `configure.connection.pswitched.tlevel.set()` | `EGPRS` | Тип канала |
| PS CScheme UL | `CONF:GSM:SIGN:CONN:PSW:CSCHeme:UL` | `configure.connection.pswitched.cscheme.ul.set()` | `MC9` | Схема кодирования UL |
| PS DL Carrier | `CONF:GSM:SIGN:CONN:PSW:SCON:ENAB:DL:CARR` | `configure.connection.pswitched.sconfig.enable.dl.carrier` | `OFF,OFF,OFF,ON,ON,OFF,OFF,OFF` | Несущие DL |
| PS DL CScheme | `CONF:GSM:SIGN:CONN:PSW:SCON:CSCH:DL:CARR` | `configure.connection.pswitched.sconfig.cscheme.dl.carrier` | `MC9,MC9,...` | Кодирование DL |

### 4.4 НЕРЕАЛИЗОВАННЫЕ — конфигурация SMS

| Параметр | SCPI | API RsCmwGsmSig | Значение | Зачем |
|----------|------|-----------------|----------|-------|
| SMS Binary Data | `CONF:GSM:SIGN1:SMS:OUTG:BIN #H{hex}` | `configure.sms.outgoing.bin.set()` | HEX EGTS-пакета | Отправка SMS |
| SMS Decoding | `CONF:GSM:SIGN:SMS:OUTG:DCODing` | `configure.sms.outgoing.dcoding.set()` | `BIT8` | 8-битное кодирование |
| SMS PID | `CONF:GSM:SIGN:SMS:OUTG:PIDentifier` | `configure.sms.outgoing.pidentifier.set()` | `#H1` | Идентификатор протокола |
| CS Action (SMS) | `CALL:GSM:SIGN:CSW:ACTion SMS` | `call.cswitched.action.set()` | `SMS` | Инициировать SMS-сессию |

### 4.5 НЕРЕАЛИЗОВАННЫЕ — чтение дополнительных данных (Sense)

| Параметр | SCPI | API RsCmwGsmSig | Зачем |
|----------|------|-----------------|-------|
| BER (битовая ошибка) | `SENSe:RReport:CSW:MBEP?` | `sense.rreport.cswitched.mbep.get()` | Качество радиоканала |
| Уровень приёма | `SENSe:RReport:RXLevel:SUB?` | `sense.rreport.rx_level.sub.get()` | Мощность сигнала |
| Качество приёма | `SENSe:RReport:RXQuality:SUB?` | `sense.rreport.rx_quality.sub.get()` | Качество соединения |
| Пропускная способность | `SENSe:CONN:ETHroughput?` | `sense.connection.ethroughput.get()` | Скорость передачи |
| IP-адрес УСВ | `SENSe:MSSInfo:MSAddr:IPv4?` | `sense.mss_info.ms_address.ipv4.get()` | Сетевые параметры |
| Класс терминала | `SENSe:MSSInfo:MSClass?` | `sense.mss_info.ms_class.get()` | Возможности УСВ |
| Статус CS-соединения | `SENSe:CONN:CSW:CONN?` | `sense.connection.cswitched.connection.get()` | Детальный статус CS |
| Статус PS-канала | `SENSe:CELL:PSWitched?` | `sense.cell.pswitched.get()` | Статус PS |
| Статус SMS исх. | `SENSe:SMS:OUTG:INFO?` | `sense.sms.outgoing.info.get()` | Статус исходящих SMS |
| Статус SMS вх. | `SENSe:SMS:INComing:INFO?` | `sense.sms.incoming.info.get()` | Статус входящих SMS |

### 4.6 НЕРЕАЛИЗОВАННЫЕ — конфигурация DAU

| Параметр | SCPI | Зачем |
|----------|------|-------|
| Meas Range | `CONF:DATA:MEAS:RAN 'GSM Sig1'` | Диапазон измерений |
| DNS Primary | `CONF:DATA:CONTrol:DNS:PRIM:STYPe Foreign` | DNS тип |
| IPv4 Address | `CONF:DATA:CONTrol:IPVFour:ADDR:TYPE DHCPv4` | Тип IP-адреса |

---

## 5. Текущая конфигурация

### 5.1 settings.json

```json
{
  "cmw500": {
    "ip": "192.168.1.100",
    "timeout": 5,
    "retries": 3,
    "sms_send_timeout": 10,
    "status_poll_interval": 2
  }
}
```

### 5.2 Что НУЖНО добавить в конфиг

| Параметр | Тип | Дефолт | Описание |
|----------|-----|--------|----------|
| `mcc` | int | `250` | Код страны |
| `mnc` | int | `60` | Код оператора |
| `rf_level_tch` | float | `-40.0` | Мощность TCH (dBm) |
| `ps_service` | str | `"TMA"` | Тип PS-сервиса |
| `ps_tlevel` | str | `"EGPRS"` | Тип PS-канала |
| `ps_cscheme_ul` | str | `"MC9"` | Схема кодирования UL |
| `ps_dl_carrier` | list[str] | `["OFF","OFF","OFF","ON","ON","OFF","OFF","OFF"]` | Несущие DL |
| `ps_dl_cscheme` | list[str] | `["MC9","MC9","MC9","MC9","MC9","MC9","MC9","MC9"]` | Кодирование DL |
| `sms_dcoding` | str | `"BIT8"` | Кодирование SMS |
| `sms_pidentifier` | int | `1` | PID SMS |
| `resource_type` | str | `"hislip"` | Тип подключения: `"vxi11"`, `"hislip"`, `"socket"` |

---

## 6. Что читаем FROM CMW-500 для оператора

### 6.1 Реализовано

| Параметр | Формат | Где отображается |
|----------|--------|-----------------|
| IMEI | строка | `cmw-status` |
| IMSI | строка | `cmw-status` |
| RSSI | `-XX dBm` | `cmw-status` |
| Статус | `"1"` / `"0"` | `cmw-status` |

### 6.2 Нужно добавить

| Параметр | Формат | Зачем | Приоритет |
|----------|--------|-------|-----------|
| **Состояние CS** | `DISConnect/CONNected/ACTive` | Понимать фазу вызова | **Высокий** |
| **Состояние PS** | `DISConnect/CONNected/ACTive` | Понимать фазу передачи данных | **Высокий** |
| **BER (битовая ошибка)** | float | Качество радиоканала, логирование | Средний |
| **Уровень приёма** | dBm | Детализация RSSI | Средний |
| **IP-адрес УСВ** | IPv4 строка | Для логирования | Низкий |
| **Класс терминала** | строка | Возможности УСВ | Низкий |
| **Статус SMS исх.** | sent/pending/failed | Контроль отправки | Средний |
| **Статус SMS вх.** | received/none | Контроль приёма | Средний |

---

## 7. Архитектура реализации

### 7.1 Подход: RsCmwGsmSig как основной драйвер

```python
class Cmw500Controller:
    _driver: RsCmwGsmSig | None  # реальное подключение
    _emulator: bool               # True = режим эмулятора

    async def connect(self):
        if self.config.ip is None:
            return  # режим без CMW

        try:
            resource = self._build_resource_string()
            self._driver = RsCmwGsmSig(resource, id_query=True, reset=False)
            self._driver.utilities.visa_timeout = int(self.config.timeout * 1000)
            self._connected = True
        except Exception:
            # Fallback на эмулятор или ошибка
            raise
```

### 7.2 `_send_scpi()` — реализация

**Вариант A: через utilities (низкоуровневый)**
```python
async def _send_scpi(self, scpi: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: self._driver.utilities.query_str(scpi)
    )
```

**Вариант B: через типизированные методы (высокоуровневый)**
```python
async def get_cs_state(self) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: self._driver.sense.connection.cswitched.connection.get()
    )
```

### 7.3 Очереди и async

PyVISA синхронный → оборачиваем в `loop.run_in_executor()` для каждого вызова.
Очередь команд (`asyncio.Queue`) остаётся — гарантирует последовательное выполнение.

---

## 8. План реализации

### Итерация 6.1: Реальное подключение ✅ (приоритет)

- [ ] `CmwConfig`: добавить `resource_type` (vxi11/hislip/socket)
- [ ] `Cmw500Controller.connect()`: инициализация `RsCmwGsmSig`
- [ ] `_send_scpi()`: реализация через `utilities.query_str()` + `run_in_executor`
- [ ] `_send_scpi_write()`: для команд без ответа (`utilities.write_str()`)
- [ ] Тесты: мок RsCmwGsmSim, проверка подключения/отключения

### Итерация 6.2: Конфигурация GSM Signaling

- [ ] Добавить все параметры из раздела 4.3 в `CmwConfig`
- [ ] Метод `configure_gsm_signaling()` — полная настройка прибора
- [ ] Метод `configure_dau()` — настройка DAU (раздел 4.6)
- [ ] Метод `configure_sms()` — настройка SMS (раздел 4.4)
- [ ] Сценарий: полная инициализация CMW-500 «с нуля»

### Итерация 6.3: Чтение состояний (Sense)

- [ ] `get_cs_state()` → состояние CS-канала
- [ ] `get_ps_state()` → состояние PS-канала
- [ ] `get_ber()` → битовая ошибка
- [ ] `get_rx_level()` → уровень приёма
- [ ] `get_rx_quality()` → качество приёма
- [ ] `get_throughput()` → пропускная способность
- [ ] `get_usv_ip()` → IP-адрес УСВ
- [ ] `get_sms_out_status()` → статус исходящих SMS
- [ ] `get_sms_in_status()` → статус входящих SMS

### Итерация 6.4: Мониторинг и EventBus

- [ ] Периодический опрос состояний (не только SMS!)
- [ ] EventBus: `cmw.cs_state_changed`, `cmw.ps_state_changed`
- [ ] EventBus: `cmw.rssi_updated`, `cmw.ber_updated`
- [ ] Кэш статусов (TTL 2-5с) — KI-046

### Итерация 6.5: eCall (голосовой канал)

- [ ] Механизм активации CS-вызова
- [ ] Передача MSD по голосовому каналу
- [ ] Сценарий №5: eCall тестирование

---

## 9. Известные проблемы и расхождения

| ID | Описание | Статус |
|----|----------|--------|
| KI-003 | Нет реального CMW-500 | Решается в 6.1 |
| KI-046 | `get_status()` без кэша | Решается в 6.4 |
| KI-042 | Проверка `is not None` вместо реального состояния | Решается в 6.3 |
| KI-048 | Redundant `and self.is_running` | Решается в 6.3 |
| CR-003 | Голосовой канал eCall не расписан | Этап 6.5 |
| CR-013 | Дублирование SMS-сессии | Вынести в фабрику |

### Расхождения в документации

| Где | Что | Правильно |
|-----|-----|-----------|
| ТЗ | `CMW:GSM:SIGN:CONN?` | ✅ Верно (сокращённая команда) |
| ARCHITECTURE.md | `CMW:GSM:SIGN:CONN:STAT?` | ❌ Нет такой команды |
| Эмулятор | статус = `"1"` | Нужно маппить: `"1"` → `CONNected` |
| CLI | статус = `"registered"` | Человекочитаемое отображение |

---

## 10. Зависимости

```toml
[project.optional-dependencies]
cmw = ["RsCmwGsmSig>=3.7.30", "RsCmwBase>=3.7.90.32"]
```

`RsCmwGsmSig` — опциональная зависимость. Без неё работает эмулятор.

---

## 11. Полезные ссылки

- [RsCmwGsmSig Docs](https://rscmwgsmsig.readthedocs.io/en/latest/)
- [RsCmwGsmSig PyPI](https://pypi.org/project/RsCmwGsmSig/)
- [RsCmwGsmMeas Docs](https://rscmwgsmsig.readthedocs.io/) — НЕ используем (PHY-измерения)
- [R&S Examples GitHub](https://github.com/Rohde-Schwarz/Examples/) — `CMW/Python/RsCmwXxx_ScpiPackages`
- [CMW Drivers Download](https://www.rohde-schwarz.com/driver/cmw500_overview/) — архив "CMW Python instrument drivers" с примерами
- [CMW500 User Manual (PDF)](http://www.vogold.com.cn/upfile/cmw500pdf/cmw500_usermanual_v3-0-14.pdf)
- [GSM Signaling Release Notes](http://www.vogold.com.cn/upfile/cmw500pdf/release%20note%20gsm%20signaling%20v3.2.70.pdf)
- [docs/comands.txt](./comands.txt) — наши SCPI-команды

---

## 12. Реальное тестирование с CMW-500 (13.04.2026)

### 12.1 Параметры реального прибора

| Параметр | Значение |
|----------|----------|
| **IP-адрес** | `192.168.2.2` |
| **VISA resource** | `TCPIP::192.168.2.2::inst0::INSTR` (не `hislip0`!) |
| **Версия ПО** | `4.0.160.40 beta` |
| **Серийный номер** | `1201.0002k50/171787` |
| **IDN** | `Rohde&Schwarz,CMW,1201.0002k50/171787,4.0.160.40 beta` |

**⚠️ Важно:** Resource string отличается от ожидаемого — `inst0::INSTR` вместо `hislip0`.

### 12.2 Что РАБОТАЕТ ✅

#### Configure (запись SCPI-команд)

Все команды конфигурации из `docs/comands.txt` работают:

| Команда | Статус | Ответ |
|---------|--------|-------|
| `CONFigure:GSM:SIGN:CELL:MCC 250` | ✅ | Записано |
| `CONFigure:GSM:SIGN:CELL:MNC 60` | ✅ | Записано |
| `CONFigure:GSM:SIGN:RFSettings:LEVel:TCH -40` | ✅ | Записано |
| `CONFigure:GSM:SIGN:CONNection:PSWitched:SERVice TMA` | ✅ | Записано |
| `CONFigure:GSM:SIGN:CONNection:PSWitched:TLEVel EGPRS` | ✅ | Записано |
| `CONFigure:GSM:SIGN:CONNection:PSWitched:CSCHeme:UL MC9` | ✅ | Записано |
| `CONFigure:GSM:SIGN:CONNection:PSWitched:SCONfig:ENABle:DL:CARRier ...` | ✅ | Записано |
| `CONFigure:GSM:SIGN:CONNection:PSWitched:SCONfig:CSCHeme:DL:CARRier ...` | ✅ | Записано |
| `CONFigure:GSM:SIGN:SMS:OUTGoing:DCODing BIT8` | ✅ | Записано |
| `CONFigure:GSM:SIGN:SMS:OUTGoing:PIDentifier #H1` | ✅ | Записано |
| `CONFigure:DATA:MEAS:RAN 'GSM Sig1'` | ✅ | Записано |
| `CONFigure:DATA:CONTrol:DNS:PRIMary:STYPe Foreign` | ✅ | Записано |
| `CONFigure:DATA:CONTrol:IPVFour:ADDRess:TYPE DHCPv4` | ✅ | Записано |
| `CONFigure:GSM:SIGN:CELL:MCC?` | ✅ | Возвращает `250` |
| `CONFigure:GSM:SIGN:CELL:MNC?` | ✅ | Возвращает `60` |

#### Чтение через utilities

| Метод | Статус |
|-------|--------|
| `*IDN?` | ✅ `Rohde&Schwarz,CMW,1201.0002k50/171787,4.0.160.40 beta` |
| `instrument_serial_number` | ✅ `1201.0002k50/171787` |

### 12.3 Что НЕ РАБОТАЕТ ❌

#### Sense API (чтение состояний)

Все Sense-команды возвращают **VISA Timeout (30 секунд)**:

| Команда | Статус | Ошибка |
|---------|--------|--------|
| `SENSe:CONNection:CSWitched:CONNection?` | ❌ | Timeout |
| `SENSe:CONN:CSW:CONN?` | ❌ | Timeout |
| `SENSe:CELL:PSWitched?` | ❌ | Timeout |
| `SENSe:CONNection:PSWitched:STATe?` | ❌ | Timeout |
| `CALL:GSM:SIGN:CSWitched:STATe?` | ❌ | Timeout + "Undefined header" |
| `CALL:GSM:SIGN:CSW:STATe?` | ❌ | Timeout |
| `SENSe:RReport:CSW:MBEP?` | ❌ | Не тестировалось (Sense) |
| `SENSe:RReport:RXLevel:SUB?` | ❌ | Не тестировалось (Sense) |
| `CMW:GSM:SIGN:RSSI?` | ❌ | Timeout |
| `CMW:GSM:SIGN:SMS:READ?` | ❌ | "Undefined header" |

#### RsCmwGsmSig типизированные API

Библиотека генерирует методы, которые не работают на этом приборе:

| API-метод | Статус |
|-----------|--------|
| `driver.call.cswitched.state.get()` | ❌ Нет метода `.state` |
| `driver.call.pswitched.state.get()` | ❌ Нет метода `.state` |
| `driver.sense.connection.cswitched.connection.get()` | ❌ Timeout |
| `driver.sense.cell.pswitched.get()` | ❌ Timeout |
| `driver.sense.rreport.cswitched.mbep.get()` | ❌ Не тестировалось |

### 12.4 Доступные API-методы (исследование через dir())

```
call.cswitched:     set_action
call.pswitched:     set_action
sense.connection.cswitched:  connection (get_attempt, get_reject)
sense.cell:         get_cerror, get_fnumber, pswitched (get_cerror)
configure.cell:     mcc, mnc, ncc (get/set), pswitched, cswitched, ...
configure.connection.pswitched:  service, tlevel, cscheme, sconfig, ...
configure.connection.pswitched.sconfig:  enable, cscheme, combined, ...
```

**Вывод:** API сгенерирован, но Sense-методы не отвечают на запросы.

### 12.5 Возможные причины неработающих Sense-команд

1. **Beta-версия ПО** — `4.0.160.40 beta` может не иметь полного GSM Signaling
2. **Отсутствует лицензия** — GSM Signaling option может быть не активирована
3. **Нет подключённого УСВ** — Sense может требовать активного соединения
4. **Версия библиотеки** — `RsCmwGsmSig>=3.7.30` может не совместима с ПО 4.0

### 12.6 Настройки VISA

| Параметр | Значение | Примечание |
|----------|----------|------------|
| `visa_timeout` | 30000 мс (30с) | По умолчанию 10000 — слишком мало |
| `instrument_status_checking` | `False` | `True` вызывает ошибки из-за старых записей в буфере |
| `opc_query_after_write` | `False` | По умолчанию False — правильно |

### 12.7 Архитектурные решения

1. **`stop_poll()` / `start_poll()`** — poll_loop нужно останавливать на время конфигурации, иначе concurrent SCPI-запросы конфликтуют за VISA-сессию
2. **SCPI напрямую** → `utilities.write_str()` / `utilities.query_str()` — надёжнее чем типизированные API
3. **Poll после конфигурации** — конфигурация должна завершиться ДО запуска poll_loop

### 12.8 Итог

| Компонент | Статус |
|-----------|--------|
| Подключение к CMW-500 | ✅ Работает |
| Конфигурация GSM (MCC, MNC, RF, PS) | ✅ Работает |
| Конфигурация SMS (DCODing, PID) | ✅ Работает |
| Конфигурация DAU | ✅ Работает |
| Чтение MCC/MNC | ✅ Работает |
| Чтение состояний (Sense) | ❌ Не работает |
| Чтение RSSI | ❌ Не работает |
| Чтение SMS | ❌ Не работает |
| Полная интеграция | ⏸️ Приостановлена |

**Дальнейшие шаги:** проверить лицензию GSM Signaling на CMW-500 или обновить ПО до стабильной версии.

### 12.9 Исправления по результатам внешнего аудита

| Параметр | Было (❌) | Стало (✅) |
|----------|-----------|------------|
| IMEI | `CMW:GSM:SIGN:IMEI?` | `CALL:GSM:SIGN1:IMEI?` |
| IMSI | `CMW:GSM:SIGN:IMSI?` | `CALL:GSM:SIGN1:IMSI?` |
| RSSI | `CMW:GSM:SIGN:RSSI?` | `CALL:GSM:SIGN1:RSSI?` |
| Status | `CMW:GSM:SIGN:CONN?` | `CALL:GSM:SIGN1:CONNection:STATe?` |
| CS state | `CALL:GSM:SIGN:CSWitched:STATe?` | `CALL:GSM:SIGN1:CONNection:CSWitched:STATe?` |
| PS state | `CALL:GSM:SIGN:PSWitched:STATe?` | `CALL:GSM:SIGN1:CONNection:PSWitched:STATe?` |
| MCC config | `write_str()` | `write_str_with_opc()` |
| MNC config | `write_str()` | `write_str_with_opc()` |

**Ключевые изменения:**

1. **`CMW:` → `CALL:GSM:SIGN1:`** — `CMW:` не SCPI-корень, правильная команда начинается с `CALL:`
2. **Добавлен инстанс `1`** — `SIGN1` вместо `SIGN`
3. **Добавлен `CONNection`** — путь `CALL:GSM:SIGN1:CONNection:CSWitched:STATe?`
4. **`opc_query_after_write = True`** — синхронизация после каждой записи
5. **`instrument_status_checking = True`** — включена проверка ошибок (после `*CLS`)
6. **`*CLS` перед включением** — очистка очереди ошибок
7. **`visa_timeout = 60000`** — увеличено до 60 секунд
8. **`write_str_with_opc()`** для конфигурационных команд — ждёт завершения
