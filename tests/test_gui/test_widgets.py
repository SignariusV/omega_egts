import pytest
from PySide6.QtWidgets import QApplication, QTableWidgetItem
from PySide6.QtCore import Qt

from gui.widgets.packet_table import PacketTable
from gui.widgets.step_list import StepList
from gui.widgets.scenario_progress import ScenarioProgress


@pytest.fixture
def packet_table(qtbot):
    """Экземпляр PacketTable."""
    table = PacketTable()
    qtbot.addWidget(table)
    return table


@pytest.fixture
def step_list(qtbot):
    """Экземпляр StepList."""
    widget = StepList()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def scenario_progress(qtbot):
    """Экземпляр ScenarioProgress."""
    widget = ScenarioProgress()
    qtbot.addWidget(widget)
    return widget


class TestPacketTable:
    """Тесты для PacketTable."""

    def test_add_packet(self, packet_table):
        """Проверка добавления пакета."""
        packet_info = {
            "time": "12:00:00",
            "direction": "RX",
            "pid": "1",
            "rn": "1",
            "size": "64 B",
            "service": "TERM_IDENTITY"
        }
        packet_table.add_packet(packet_info)
        assert packet_table.rowCount() == 1
        assert packet_table.item(0, 0).text() == "12:00:00"
        assert "RX" in packet_table.item(0, 1).text()

    def test_add_multiple_packets(self, packet_table):
        """Проверка добавления нескольких пакетов."""
        for i in range(5):
            packet_table.add_packet({
                "time": f"12:00:0{i}",
                "direction": "TX" if i % 2 == 0 else "RX",
                "pid": str(i),
                "rn": str(i),
                "size": "64 B",
                "service": "TEST"
            })
        assert packet_table.rowCount() == 5

    def test_filter_direction(self, packet_table):
        """Проверка фильтрации по направлению."""
        packets = [
            {"time": "12:00:00", "direction": "RX", "pid": "1", "rn": "1", "size": "64 B", "service": "TEST"},
            {"time": "12:00:01", "direction": "TX", "pid": "2", "rn": "2", "size": "32 B", "service": "TEST"},
            {"time": "12:00:02", "direction": "RX", "pid": "3", "rn": "3", "size": "48 B", "service": "TEST"},
        ]
        for p in packets:
            packet_table.add_packet(p)

        # Фильтр RX
        packet_table.set_filter(direction="RX")
        assert packet_table.isRowHidden(0) == False
        assert packet_table.isRowHidden(1) == True
        assert packet_table.isRowHidden(2) == False

        # Фильтр TX
        packet_table.set_filter(direction="TX")
        assert packet_table.isRowHidden(0) == True
        assert packet_table.isRowHidden(1) == False
        assert packet_table.isRowHidden(2) == True

        # Сброс фильтра
        packet_table.set_filter(direction="Все")
        assert packet_table.isRowHidden(0) == False
        assert packet_table.isRowHidden(1) == False
        assert packet_table.isRowHidden(2) == False

    def test_filter_text(self, packet_table):
        """Проверка текстового поиска."""
        packets = [
            {"time": "12:00:00", "direction": "RX", "pid": "1", "rn": "1", "size": "64 B", "service": "TERM_IDENTITY"},
            {"time": "12:00:01", "direction": "TX", "pid": "2", "rn": "2", "size": "32 B", "service": "RECORD_RESP"},
        ]
        for p in packets:
            packet_table.add_packet(p)

        # Поиск по service
        packet_table.set_filter(text="TERM")
        assert packet_table.isRowHidden(0) == False
        assert packet_table.isRowHidden(1) == True

        # Сброс
        packet_table.set_filter(text="")
        assert packet_table.isRowHidden(0) == False
        assert packet_table.isRowHidden(1) == False


class TestStepList:
    """Тесты для StepList."""

    def test_set_steps(self, step_list):
        """Проверка загрузки шагов."""
        steps = [
            {"name": "Terminal Identity", "type": "expect"},
            {"name": "Send Auth Response", "type": "send"},
            {"name": "Expect AUTH_INFO", "type": "expect"}
        ]
        step_list.set_steps(steps)
        assert step_list.rowCount() == 3
        assert "Terminal Identity" in step_list.item(0, 1).text()
        assert step_list.item(0, 2).text() == "expect"

    def test_update_step_status(self, step_list):
        """Проверка обновления статуса шага."""
        steps = [{"name": "Step1", "type": "expect"}]
        step_list.set_steps(steps)
        step_list.update_step_status("Step1", "PASS")
        assert "PASS" in step_list.item(0, 3).text()

    def test_update_nonexistent_step(self, step_list):
        """Проверка обновления несуществующего шага."""
        steps = [{"name": "Step1", "type": "expect"}]
        step_list.set_steps(steps)
        # Не должно падать
        step_list.update_step_status("Unknown", "PASS")
        assert step_list.rowCount() == 1


class TestScenarioProgress:
    """Тесты для ScenarioProgress."""

    def test_initial_state(self, scenario_progress):
        """Проверка начального состояния."""
        assert "Не выбран" in scenario_progress.name_label.text()
        assert scenario_progress.progress_bar.value() == 0

    def test_set_scenario(self, scenario_progress):
        """Проверка установки сценария."""
        scenario_progress.set_scenario("Test Scenario", 10)
        assert "Test Scenario" in scenario_progress.name_label.text()
        assert scenario_progress.total_steps == 10

    def test_update_progress(self, scenario_progress):
        """Проверка обновления прогресса."""
        scenario_progress.set_scenario("Test", 10)
        scenario_progress.update_progress(completed=5, errors=1)
        assert scenario_progress.progress_bar.value() == 50
        assert "5/10" in scenario_progress.counter_label.text()
        assert "1" in scenario_progress.errors_label.text()

    def test_set_status(self, scenario_progress):
        """Проверка установки статуса."""
        scenario_progress.set_status("PASS")
        assert "ЗАВЕРШЁН" in scenario_progress.status_label.text()

    def test_reset(self, scenario_progress):
        """Проверка сброса виджета."""
        scenario_progress.set_scenario("Test", 10)
        scenario_progress.update_progress(5, 0)
        scenario_progress.reset()
        assert "Не выбран" in scenario_progress.name_label.text()
        assert scenario_progress.progress_bar.value() == 0
