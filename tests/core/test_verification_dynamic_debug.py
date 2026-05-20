"""Тест для воспроизведения ошибки 'str' object has no attribute 'to_bytes'."""
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
    # Загружаем переменные из сценария
    for k, v in data.get("variables", {}).items():
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
    mgr.load(scenario_path)

    # Проверяем что переменные загружены в контекст
    assert mgr.context.get("packet_id") == 27, f"packet_id = {mgr.context.get('packet_id')}"
    assert mgr.context.get("record_id") == 42, f"record_id = {mgr.context.get('record_id')}"
    assert mgr.context.get("service_type") == 4, f"service_type = {mgr.context.get('service_type')}"
    assert mgr.context.get("recipient_service_type") == 4, f"recipient_service_type = {mgr.context.get('recipient_service_type')}"
    print("PASS: All variables loaded correctly")

    # Пробуем собрать первый шаг
    step = mgr.steps[0]
    packet_bytes = step._build_from_template_bytes(mgr.context)
    print(f"SUCCESS: packet_bytes = {packet_bytes.hex()}")


if __name__ == "__main__":
    test_verification_dynamic_step1()
    print("\n" + "=" * 60 + "\n")
    test_scenario_manager_loads_variables()
