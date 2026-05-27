"""Тест для воспроизведения ошибки 'str' object has no attribute 'to_bytes'."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.scenario import SendStep, ScenarioContext, ScenarioManager, StepFactory
from core.scenario_parser import ScenarioParserFactory, ScenarioParserRegistry, ScenarioParserV1


def test_verification_dynamic_step1():
    """Воспроизвести ошибку при выполнении первого шага verification_dynamic."""
    scenario_path = Path(__file__).resolve().parent.parent.parent / "scenarios" / "verification_dynamic" / "scenario.json"
    data = json.loads(scenario_path.read_text(encoding="utf-8"))

    registry = ScenarioParserRegistry()
    registry.register("1", ScenarioParserV1)
    factory = ScenarioParserFactory(registry)
    parser = factory.detect_and_create(data)
    parser.load(data)
    steps = parser.get_steps()

    step_def = steps[0]
    print(f"\nStep: {step_def.name}")
    print(f"Build keys: {list(step_def.build.keys())}")
    print(f"Packet dict: {json.dumps(step_def.build.get('packet', {}), indent=2, ensure_ascii=False)}")

    ctx = ScenarioContext(scenario_version="1", gost_version="2015")
    # Загружаем переменные из сценария (с поддержкой формата {"start": N, "auto": bool} и {"resolver": "name"})
    for k, v in data.get("variables", {}).items():
        if isinstance(v, dict) and "start" in v:
            ctx.set(k, v["start"], auto_increment=v.get("auto", False))
            print(f"Variable set: {k} = {v['start']!r} (auto_increment={v.get('auto', False)})")
        elif isinstance(v, dict) and "resolver" in v:
            # В тесте используем заглушку — резолвер вернёт эталонное значение
            resolved = "200.20.2.171:9090"
            ctx.set(k, resolved)
            print(f"Variable set: {k} = {resolved!r} (resolved from '{v['resolver']}')")
        else:
            ctx.set(k, v)
            print(f"Variable set: {k} = {v!r} (type={type(v).__name__})")

    step = SendStep(
        name=step_def.name,
        channel=step_def.channel,
        timeout=step_def.timeout,
        packet_file=step_def.packet_file,
        build=step_def.build,
    )

    # Пробуем собрать пакет
    try:
        packet_bytes = step._build_from_template_bytes(ctx)
        print(f"\nSUCCESS: packet_bytes = {packet_bytes.hex()}")
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_scenario_manager_loads_variables():
    """Проверить что ScenarioManager.load() загружает variables из JSON."""
    scenario_path = Path(__file__).resolve().parent.parent.parent / "scenarios" / "verification_dynamic" / "scenario.json"

    registry = ScenarioParserRegistry()
    registry.register("1", ScenarioParserV1)
    factory = ScenarioParserFactory(registry)

    mgr = ScenarioManager(parser_factory=factory)
    # Регистрируем резолвер для server_address (эталонное значение для теста)
    mgr.register_resolver("server_address", lambda: "200.20.2.171:9090")
    mgr.load(scenario_path)

    # Проверяем что переменные загружены в контекст
    assert mgr.context.get("packet_id") == 27, f"packet_id = {mgr.context.get('packet_id')}"
    assert mgr.context.get("record_id") == 42, f"record_id = {mgr.context.get('record_id')}"
    assert mgr.context.get("service_type") == 4, f"service_type = {mgr.context.get('service_type')}"
    assert mgr.context.get("recipient_service_type") == 4, f"recipient_service_type = {mgr.context.get('recipient_service_type')}"
    assert mgr.context.get("server_address_dt") == "200.20.2.171:9090", f"server_address_dt = {mgr.context.get('server_address_dt')}"
    print("PASS: All variables loaded correctly")

    # Пробуем собрать первый шаг
    step = mgr.steps[0]
    packet_bytes = step._build_from_template_bytes(mgr.context)
    print(f"SUCCESS: packet_bytes = {packet_bytes.hex()}")


def test_sendstep_captures_sent_vars():
    """SendStep с build-template сохраняет sent_cid/sent_pid/sent_rn в контекст."""
    scenario_path = Path(__file__).resolve().parent.parent.parent / "scenarios" / "verification_modern" / "scenario.json"
    data = json.loads(scenario_path.read_text(encoding="utf-8"))

    registry = ScenarioParserRegistry()
    registry.register("1", ScenarioParserV1)
    factory = ScenarioParserFactory(registry)
    parser = factory.detect_and_create(data)
    parser.load(data)
    steps = parser.get_steps()

    ctx = ScenarioContext(scenario_version="1", gost_version="2015")
    # Загружаем переменные
    for k, v in data.get("variables", {}).items():
        if isinstance(v, dict) and "start" in v:
            ctx.set(k, v["start"], auto_increment=v.get("auto", False))
        elif isinstance(v, dict) and "resolver" in v:
            ctx.set(k, "200.20.2.171:9090")
        else:
            ctx.set(k, v)

    from core.event_bus import EventBus
    bus = EventBus()

    step = SendStep(
        name=steps[0].name,
        channel=steps[0].channel,
        timeout=steps[0].timeout,
        build=steps[0].build,
    )

    # Execute send — эмулируем command.sent
    async def _run():
        async def emit_sent():
            await asyncio.sleep(0.01)
            await bus.emit("command.sent", {"step_name": step.name, "packet_bytes": b"test"})

        import asyncio
        task = asyncio.create_task(emit_sent())
        result, details = await step.execute(ctx, bus, timeout=2.0)
        await task
        return result

    import asyncio
    result = asyncio.run(_run())

    assert result == "PASS"
    # Проверяем что sent_* переменные установлены
    assert ctx.get("sent_pid") == 27, f"sent_pid = {ctx.get('sent_pid')}"
    assert ctx.get("sent_rn") == 42, f"sent_rn = {ctx.get('sent_rn')}"
    assert ctx.get("sent_cid") == 0, f"sent_cid = {ctx.get('sent_cid')}"
    assert ctx.get("sent_sid") == 0, f"sent_sid = {ctx.get('sent_sid')}"


if __name__ == "__main__":
    test_verification_dynamic_step1()
    print("\n" + "=" * 60 + "\n")
    test_scenario_manager_loads_variables()
    print("\n" + "=" * 60 + "\n")
    test_sendstep_captures_sent_vars()
