import pytest
from gui.utils.validators import validate_scenario, validate_json_string


class TestValidateScenario:
    """Тесты для validate_scenario."""

    def test_valid_scenario(self):
        """Проверка корректного сценария."""
        scenario = {
            "name": "Test",
            "version": "1",
            "steps": [
                {"type": "expect", "match": {"service": 1}},
                {"type": "send", "data": "some data"}
            ]
        }
        is_valid, errors = validate_scenario(scenario)
        assert is_valid
        assert len(errors) == 0

    def test_missing_name(self):
        """Проверка отсутствия обязательного поля name."""
        scenario = {"version": "1", "steps": []}
        is_valid, errors = validate_scenario(scenario)
        assert not is_valid
        assert any("name" in e for e in errors)

    def test_missing_version(self):
        """Проверка отсутствия поля version."""
        scenario = {"name": "Test", "steps": []}
        is_valid, errors = validate_scenario(scenario)
        assert not is_valid
        assert any("version" in e for e in errors)

    def test_missing_steps(self):
        """Проверка отсутствия поля steps."""
        scenario = {"name": "Test", "version": "1"}
        is_valid, errors = validate_scenario(scenario)
        assert not is_valid
        assert any("steps" in e for e in errors)

    def test_invalid_step_type(self):
        """Проверка неизвестного типа шага."""
        scenario = {
            "name": "Test",
            "version": "1",
            "steps": [{"type": "unknown"}]
        }
        is_valid, errors = validate_scenario(scenario)
        assert not is_valid
        assert any("неизвестный тип" in e for e in errors)

    def test_expect_without_match(self):
        """Проверка expect без поля match."""
        scenario = {
            "name": "Test",
            "version": "1",
            "steps": [{"type": "expect"}]
        }
        is_valid, errors = validate_scenario(scenario)
        assert not is_valid
        assert any("match" in e for e in errors)

    def test_send_without_data(self):
        """Проверка send без поля data."""
        scenario = {
            "name": "Test",
            "version": "1",
            "steps": [{"type": "send"}]
        }
        is_valid, errors = validate_scenario(scenario)
        assert not is_valid
        assert any("data" in e for e in errors)

    def test_delay_step(self):
        """Проверка шага delay (без дополнительных полей)."""
        scenario = {
            "name": "Test",
            "version": "1",
            "steps": [{"type": "delay", "duration": 5}]
        }
        is_valid, errors = validate_scenario(scenario)
        # delay не требует обязательных полей, кроме type
        assert is_valid


class TestValidateJsonString:
    """Тесты для validate_json_string."""

    def test_valid_json(self):
        """Проверка корректного JSON."""
        json_str = '{"name": "Test", "version": "1", "steps": []}'
        is_valid, result = validate_json_string(json_str)
        assert is_valid
        assert isinstance(result, dict)

    def test_invalid_json(self):
        """Проверка некорректного JSON."""
        json_str = '{"name": "Test", "version": "1",}'  # лишняя запятая
        is_valid, result = validate_json_string(json_str)
        assert not is_valid
        assert "Ошибка разбора JSON" in result

    def test_json_not_object(self):
        """Проверка JSON, который не является объектом."""
        json_str = '[1, 2, 3]'
        is_valid, result = validate_json_string(json_str)
        assert not is_valid
        assert "должен представлять собой объект" in result
