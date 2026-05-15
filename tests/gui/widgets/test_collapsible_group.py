# OMEGA_EGTS GUI Tests
"""Tests for CollapsibleGroupBox widget."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
from gui.widgets.collapsible_group import CollapsibleGroupBox


def test_collapsible_group_creation(qtbot):
    """Test that CollapsibleGroupBox creates correctly."""
    widget = CollapsibleGroupBox("Test Group")
    qtbot.addWidget(widget)

    assert widget._title == "Test Group"
    assert not widget.is_collapsed()
    assert widget._toggle_btn is not None
    assert widget._content_container is not None


def test_collapsible_group_toggle(qtbot):
    """Test toggling collapse state."""
    widget = CollapsibleGroupBox("Test Group")
    qtbot.addWidget(widget)
    widget.show()

    # Initially expanded
    assert not widget.is_collapsed()
    # isVisible might be False if window not shown, check internal flag
    # and content container visibility (if widget is shown)
    if widget.isVisible():
        assert widget._content_container.isVisible()

    # Click toggle button to collapse
    widget._toggle_btn.click()
    assert widget.is_collapsed()
    if widget.isVisible():
        assert not widget._content_container.isVisible()

    # Click again to expand
    widget._toggle_btn.click()
    assert not widget.is_collapsed()
    if widget.isVisible():
        assert widget._content_container.isVisible()


def test_collapsible_group_set_content_widget(qtbot):
    """Test setting content widget."""
    widget = CollapsibleGroupBox("Test Group")
    qtbot.addWidget(widget)
    widget.show()

    inner_widget = QLabel("Content")
    widget.set_content_widget(inner_widget)

    # Check that inner widget is inside content container
    assert inner_widget.parent() == widget._content_container
    # Check that it is in the layout of content_container
    layout = widget._content_container.layout()
    assert layout is not None
    assert layout.count() >0
    # Check the widget is the first item in layout
    item = layout.itemAt(0)
    assert item is not None
    assert item.widget() == inner_widget


def test_collapsible_group_signal(qtbot):
    """Test that toggled signal is emitted."""
    widget = CollapsibleGroupBox("Test Group")
    qtbot.addWidget(widget)

    signals = []
    widget.toggled.connect(lambda state: signals.append(state))

    widget._toggle_btn.click()  # collapse
    assert len(signals) == 1
    assert signals[0] is False  # collapsed = True, signal emits not collapsed state

    widget._toggle_btn.click()  # expand
    assert len(signals) == 2
    assert signals[1] is True


def test_collapsible_group_set_collapsed(qtbot):
    """Test set_collapsed method."""
    widget = CollapsibleGroupBox("Test Group")
    qtbot.addWidget(widget)
    widget.show()

    widget.set_collapsed(True)
    assert widget.is_collapsed()
    if widget.isVisible():
        assert not widget._content_container.isVisible()

    widget.set_collapsed(False)
    assert not widget.is_collapsed()
    if widget.isVisible():
        assert widget._content_container.isVisible()
