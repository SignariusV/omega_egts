"""Тестирование команд CMW-500.

Использование:
    python test_cmw_commands.py                    # localhost:192.168.2.2
    python test_cmw_commands.py 192.168.1.100      # другой IP
    python test_cmw_commands.py --simulate         # режим симуляции
"""
import sys
import argparse
from RsCmwGsmSig import RsCmwGsmSig


def main():
    parser = argparse.ArgumentParser(description="Тестирование CMW-500")
    parser.add_argument("ip", nargs="?", default="192.168.2.2", help="IP-адрес CMW-500")
    parser.add_argument("--simulate", action="store_true", help="Режим симуляции")
    args = parser.parse_args()

    print(f"=== CMW-500 Тестирование ===")
    print(f"IP: {args.ip}")
    print(f"Режим: {'Симуляция' if args.simulate else 'Реальный прибор'}")
    print()

    try:
        d = RsCmwGsmSig(
            f"TCPIP::{args.ip}::inst0::INSTR",
            id_query=not args.simulate,
            reset=False,
            options="Simulate=True" if args.simulate else None,
        )
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        return 1

    d.utilities.visa_timeout = 60000
    d.utilities.write_str("*CLS")
    d.utilities.instrument_status_checking = True
    d.utilities.opc_query_after_write = True

    print(f"✅ Подключено")
    print(f"  IDN: {d.utilities.idn_string}")
    print(f"  Serial: {d.utilities.instrument_serial_number}")
    print()

    # ── Configure (запись) ──
    print("--- Configure ---")
    write_cmds = [
        ("MCC 250", "CONFigure:GSM:SIGN1:CELL:MCC 250"),
        ("MNC 60", "CONFigure:GSM:SIGN1:CELL:MNC 60"),
        ("RF -40", "CONFigure:GSM:SIGN1:RFSettings:LEVel:TCH -40"),
        ("PS Service TMA", "CONFigure:GSM:SIGN1:CONNection:PSWitched:SERVice TMA"),
        ("PS TLevel EGPRS", "CONFigure:GSM:SIGN1:CONNection:PSWitched:TLEVel EGPRS"),
        ("PS CScheme UL MC9", "CONFigure:GSM:SIGN1:CONNection:PSWitched:CSCHeme:UL MC9"),
        ("SMS DCODing BIT8", "CONFigure:GSM:SIGN:SMS:OUTGoing:DCODing BIT8"),
        ("SMS PID #H1", "CONFigure:GSM:SIGN:SMS:OUTGoing:PIDentifier #H1"),
        ("DAU Range", "CONFigure:DATA:MEAS:RAN 'GSM Sig1'"),
        ("DAU DNS", "CONFigure:DATA:CONTrol:DNS:PRIMary:STYPe Foreign"),
        ("DAU DHCP", "CONFigure:DATA:CONTrol:IPVFour:ADDRess:TYPE DHCPv4"),
    ]
    for name, cmd in write_cmds:
        try:
            d.utilities.write_str_with_opc(cmd)
            print(f"  ✅ {name}")
        except Exception as e:
            err = str(e).replace('\n', ' ')[:80]
            print(f"  ❌ {name}: {err}")

    print()

    # ── Чтение ──
    print("--- Чтение ---")
    read_cmds = [
        ("IMEI", "SENSe:GSM:SIGN1:MSSinfo:IMEI?"),
        ("IMSI", "SENSe:GSM:SIGN1:MSSinfo:IMSI?"),
        ("RSSI GSM Cell1", "SENSe:GSM:SIGN1:RREPort:NCELl:GSM:CELL1?"),
        ("RSSI Range GSM Cell1", "SENSe:GSM:SIGN1:RREPort:NCELl:GSM:CELL1:RANGe?"),
        ("Status", "SOURce:GSM:SIGN:CELL:STATe:ALL?"),
        ("CS State", "FETCh:GSM:SIGN:CSWitched:STATe?"),
        ("PS State", "FETCh:GSM:SIGN:PSWitched:STATe?"),
        ("MCC?", "CONFigure:GSM:SIGN:CELL:MCC?"),
        ("MNC?", "CONFigure:GSM:SIGN:CELL:MNC?"),
    ]
    for name, cmd in read_cmds:
        try:
            result = d.utilities.query_str_with_opc(cmd).strip()
            print(f"  ✅ {name}: '{result}'")
        except Exception as e:
            err = str(e).replace('\n', ' ')[:80]
            print(f"  ❌ {name}: {err}")

    print()

    # ── Ошибки прибора ──
    print("--- Ошибки прибора ---")
    try:
        errors = d.utilities.query_str("SYSTem:ERRor:ALL?").strip()
        print(f"  {errors}")
    except Exception as e:
        print(f"  ❌ {e}")

    print()



    d.close()
    print("✅ Готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())





"""=== CMW-500 Тестирование ===
IP: 192.168.2.2
Режим: Реальный прибор

✅ Подключено
  IDN: Rohde&Schwarz,CMW,1201.0002k50/168170,3.7.140
  Serial: 1201.0002k50/168170

--- Configure ---
  ✅ MCC 250
  ✅ MNC 60
  ✅ RF -40
  ✅ PS Service TMA
  ✅ PS TLevel EGPRS
  ✅ PS CScheme UL MC9
  ✅ SMS DCODing BIT8
  ✅ SMS PID #H1
  ✅ DAU Range
  ✅ DAU DNS
  ✅ DAU DHCP

--- Чтение ---
  ✅ IMEI: '"860803066444684"'
  ✅ IMSI: '"250600003413771"'
  ✅ RSSI GSM Cell1: 'INV'
  ✅ RSSI Range GSM Cell1: 'INV,INV'
  ✅ Status: 'ON,ADJ'
  ✅ CS State: 'SYNC'
  ✅ PS State: 'ATT'
  ✅ MCC?: '250'
  ✅ MNC?: '60'

--- Ошибки прибора ---
  0,"No error"

✅ Готово"""