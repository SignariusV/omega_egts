"""Tests for HexDumpWidget."""

import pytest
from PySide6.QtWidgets import QApplication
from gui.utils.hex_viewer import HexDumpWidget


class TestHexDumpWidgetInit:
    def test_init_creates_widget(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        assert widget.isReadOnly() == True

    def test_default_text(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        assert "(no data)" in widget.toPlainText()


class TestHexDumpWidgetData:
    def test_set_hex_data(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        widget.set_hex_data("0100000B0021001B00")
        text = widget.toPlainText()
        assert len(text) > 0
        assert "01" in text

    def test_contains_offset(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        widget.set_hex_data("0100000B0021001B00")
        text = widget.toPlainText()
        assert "0000:" in text

    def test_multiple_lines(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        # 32 bytes = 2 lines of 16 bytes
        long_hex = "01" * 32
        widget.set_hex_data(long_hex)
        text = widget.toPlainText()
        assert "0000:" in text
        assert "0010:" in text

    def test_empty_hex(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        widget.set_hex_data("")
        assert "(no data)" in widget.toPlainText()

    def test_invalid_hex(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        widget.set_hex_data("ZZZ")
        assert "(invalid hex)" in widget.toPlainText()

    def test_none_hex(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        widget.set_hex_data(None)
        assert "(no data)" in widget.toPlainText()


class TestHexDumpWidgetHighlight:
    def test_clear_highlight_does_not_crash(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        widget.set_hex_data("0100000B0021001B00")
        widget.clear_highlight()

    def test_highlight_range_does_not_crash(self, qtbot):
        widget = HexDumpWidget()
        qtbot.addWidget(widget)
        widget.set_hex_data("0100000B0021001B00")
        widget.highlight(0, 3)
