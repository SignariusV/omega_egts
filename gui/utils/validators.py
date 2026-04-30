from typing import Union


def validate_scenario(scenario: dict) -> tuple[bool, list[str]]:
    """Проверка структуры сценария.

    Возвращает (is_valid, list_of_errors).
    """
    errors = []

    # Обязательные поля
    required_fields = ["name", "version", "steps"]
    for field in required_fields:
        if field not in scenario:
            errors.append(f"Отсутствует обязательное поле: {field}")

    # Проверка шагов
    if "steps" in scenario:
        steps = scenario["steps"]
        if not isinstance(steps, list):
            errors.append("Поле 'steps' должно быть списком")
        else:
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    errors.append(f"Шаг {i}: должен быть объектом")
                    continue

                if "type" not in step:
                    errors.append(f"Шаг {i}: отсутствует поле 'type'")
                else:
                    step_type = step["type"]
                    if step_type not in ["expect", "send", "delay"]:
                        errors.append(f"Шаг {i}: неизвестный тип '{step_type}'")

                # Для expect и send нужно поле match/data
                if step_type in ["expect", "send"]:
                    if step_type == "expect" and "match" not in step:
                        errors.append(f"Шаг {i}: для expect требуется поле 'match'")
                    if step_type == "send" and "data" not in step:
                        errors.append(f"Шаг {i}: для send требуется поле 'data'")

    return len(errors) == 0, errors


def validate_json_string(json_str: str) -> tuple[bool, Union[dict, str, list]]:
    """Валидация JSON-строки.

    Возвращает (is_valid, data_or_errors).
    При успехе возвращает (True, dict).
    При ошибке валидации возвращает (False, list_of_errors).
    При ошибке JSON возвращает (False, error_message).
    """
    import json
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return False, "JSON должен представлять собой объект"
        is_valid, errors = validate_scenario(data)
        if is_valid:
            return True, data
        else:
            return False, errors
    except json.JSONDecodeError as e:
        return False, f"Ошибка разбора JSON: {str(e)}"
