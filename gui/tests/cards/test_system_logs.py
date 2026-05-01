# OMEGA_EGTS GUI
import pytest
import logging
from PySide6.QtWidgets import QApplication
from gui.dashboard.cards.system_logs import SystemLogsCard
from gui.widgets.log_viewer import LogViewer
from gui.utils.qt_log_handler import QLogHandler
from gui.dashboard.card_base import DisplayState


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class TestQLogHandler:
    def test_handler_emits_signal(self, qtbot):
        handler = QLogHandler()
        emitted = []
        handler.log_message.connect(lambda m: emitted.append(m))
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Test message", args=(), exc_info=None
        )
        handler.emit(record)
        assert len(emitted) == 1
        assert emitted[0]["message"] == "Test message"
        assert emitted[0]["level"] == "INFO"

    def test_handler_contains_timestamp(self, qtbot):
        handler = QLogHandler()
        emitted = []
        handler.log_message.connect(lambda m: emitted.append(m))
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="Warning msg", args=(), exc_info=None
        )
        handler.emit(record)
        assert "timestamp" in emitted[0]


class TestLogViewer:
    def test_initial_state(self):
        viewer = LogViewer()
        assert viewer.get_content() == ""

    def test_append_log(self):
        viewer = LogViewer()
        viewer.append_log("ERROR", "Test error", 1700000000.0)
        content = viewer.get_content()
        assert "ERROR" in content
        assert "Test error" in content

    def test_clear(self):
        viewer = LogViewer()
        viewer.append_log("INFO", "Test")
        viewer.clear()
        assert viewer.get_content() == ""


class TestSystemLogsCard:
    def test_initial_state(self, qtbot):
        card = SystemLogsCard()
        qtbot.addWidget(card)
        assert card.title == "System Logs"

    def test_compact_mode_shows_edit(self, qtbot):
        card = SystemLogsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.COMPACT)
        assert card._current_widget == card._compact_widget
        assert card._compact_edit is not None

    def test_expanded_mode_shows_viewer(self, qtbot):
        card = SystemLogsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        assert card._current_widget == card._expanded_widget
        assert card._log_viewer is not None

    def test_log_handler_updates_viewer(self, qtbot):
        card = SystemLogsCard()
        qtbot.addWidget(card)
        card._on_log_message({"level": "INFO", "message": "Test log message", "timestamp": 1700000000})
        content = card._log_viewer.get_content()
        assert "Test log message" in content

    def test_log_handler_updates_compact(self, qtbot):
        card = SystemLogsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.COMPACT)
        logging.warning("Compact test")
        qtbot.wait(50)
        content = card._compact_edit.toPlainText()
        assert "Compact test" in content

    def test_clear_button(self, qtbot):
        card = SystemLogsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        logging.info("Test")
        qtbot.wait(50)
        card._clear_btn.click()
        assert card._log_viewer.get_content() == ""

    def test_level_filter(self, qtbot):
        card = SystemLogsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        card._level_combo.setCurrentText("ERROR")
        logging.info("Should not appear")
        logging.error("Should appear")
        qtbot.wait(50)
        content = card._log_viewer.get_content()
        assert "Should appear" in content

    def test_get_set_state(self, qtbot):
        card = SystemLogsCard()
        qtbot.addWidget(card)
        state = card.get_state()
        assert "level" in state
        card.set_state({"level": "WARNING"})
        assert card._level_combo.currentText() == "WARNING"