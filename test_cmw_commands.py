"""Тестирование команд CMW-500.

Использование:
    python test_cmw_commands.py                    # localhost:192.168.2.2
    python test_cmw_commands.py 192.168.1.100      # другой IP
    python test_cmw_commands.py --simulate         # режим симуляции
"""
import argparse
import sys

from RsCmwGsmSig import RsCmwGsmSig


def main():
    parser = argparse.ArgumentParser(description="Тестирование CMW-500")
    parser.add_argument("ip", nargs="?", default="192.168.2.2", help="IP-адрес CMW-500")
    parser.add_argument("--simulate", action="store_true", help="Режим симуляции")
    args = parser.parse_args()

    print("=== CMW-500 Тестирование ===")
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

    print("✅ Подключено")
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
        ("SMS DCODing BIT8", "CONFigure:GSM:SIGN1:SMS:OUTGoing:DCODing BIT8"),
        ("SMS PID #H1", "CONFigure:GSM:SIGN1:SMS:OUTGoing:PIDentifier #H1"),
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
        ("IMEI", "CALL:GSM:SIGN1:IMEI?"),
        ("IMSI", "CALL:GSM:SIGN1:IMSI?"),
        ("RSSI", "CALL:GSM:SIGN1:RSSI?"),
        ("Status", "CALL:GSM:SIGN1:CONNection:STATe?"),
        ("CS State", "CALL:GSM:SIGN1:CONNection:CSWitched:STATe?"),
        ("PS State", "CALL:GSM:SIGN1:CONNection:PSWitched:STATe?"),
        ("MCC?", "CONFigure:GSM:SIGN1:CELL:MCC?"),
        ("MNC?", "CONFigure:GSM:SIGN1:CELL:MNC?"),
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

    # ── Help headers (первые 500 символов) ──
    print("--- Поддерживаемые команды (GSM/Signaling) ---")
    try:
        headers = d.utilities.query_str("SYSTem:HELP:HEADers?")
        lines = [l.strip() for l in headers.strip().split('\n') if 'GSM' in l.upper() or 'SIGN' in l.upper()]
        for line in lines[:50]:
            print(f"  {line}")
        if len(lines) > 50:
            print(f"  ... и ещё {len(lines) - 50} команд")
    except Exception as e:
        err = str(e).replace('\n', ' ')[:80]
        print(f"  ❌ {err}")

    print()

    d.close()
    print("✅ Готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
