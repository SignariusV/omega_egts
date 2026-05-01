# OMEGA_EGTS GUI
import pytest
from PySide6.QtCore import Qt
from gui.dashboard.card_base import BaseCard, DisplayState


class TestBaseCard:
    def test_initial_state(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        assert not card._collapsed
        assert card.title == "Test"

    def test_collapse_expand(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        card.collapse()
        assert card._collapsed
        card.expand()
        assert not card._collapsed

    def test_resize_minimum(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        card.resize(100, 80)
        assert card.width() >= 240
        assert card.height() >= 100

    def test_compact_state(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        card.show()
        card.resize(300, 200)
        qtbot.wait(10)
        assert card._display_state == DisplayState.COMPACT

    def test_expanded_state(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        card.resize(600, 200)
        assert card._display_state == DisplayState.EXPANDED