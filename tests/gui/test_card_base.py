# OMEGA_EGTS GUI
import pytest
from gui.dashboard.card_base import BaseCard, DisplayState


class TestBaseCard:
    def test_initial_state(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        assert card._collapsed is False
        assert card.title == "Test"
        assert card._display_state == DisplayState.EXPANDED

    def test_collapse_expand(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        card.collapse()
        assert card._collapsed is True
        card.expand()
        assert card._collapsed is False

    def test_resize_minimum(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        card.resize(100, 80)
        assert card.width() >= 240
        assert card.height() >= 100

    def test_collapse_changes_grid_size(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        assert card.grid_size == (4, 4)

        card.collapse()
        assert card.grid_size == (1, 2)

        card.expand()
        assert card.grid_size == (4, 4)

    def test_toggle_collapse(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        assert card._collapsed is False

        card.toggle_collapse()
        assert card._collapsed is True

        card.toggle_collapse()
        assert card._collapsed is False

    def test_collapse_button_changes_text(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)

        assert card._collapse_btn.text() == "\u25BC"
        card.collapse()
        assert card._collapse_btn.text() == "\u25B2"
        card.expand()
        assert card._collapse_btn.text() == "\u25BC"

    def test_grid_position(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        assert card.grid_position == (0, 0)

        card.set_grid_position(2, 3)
        assert card.grid_position == (2, 3)

    def test_set_grid_size(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)

        received = []
        card.grid_size_changed.connect(lambda r, c: received.append((r, c)))
        card.set_grid_size(3, 5)

        assert received == [(3, 5)]
        assert card.grid_size == (3, 5)

    def test_card_id_custom(self, qtbot):
        card = BaseCard("Test", card_id="custom_id")
        assert card.card_id == "custom_id"

    def test_visibility_signals(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)

        received = []
        card.card_visibility_changed.connect(lambda v: received.append(v))

        card.show()
        assert received == [True]

        card.hide()
        assert received == [True, False]

    

    def test_title_property(self, qtbot):
        card = BaseCard("Original Title")
        qtbot.addWidget(card)
        assert card.title == "Original Title"

        card.title = "New Title"
        assert card.title == "New Title"
        assert card._title_label.text() == "New Title"

    def test_minimum_size(self, qtbot):
        card = BaseCard("Test")
        qtbot.addWidget(card)
        assert card.minimumSize().width() >= 240
        assert card.minimumSize().height() >= 100