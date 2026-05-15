# OMEGA_EGTS GUI
import pytest
from gui.dashboard.container import DashboardContainer
from gui.dashboard.sidebar import CardSidebar
from gui.dashboard.card_base import BaseCard


class TestCardSidebar:
    def test_initialization(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card1 = BaseCard("Card 1", card_id="card_1")
        card2 = BaseCard("Card 2", card_id="card_2")
        container.add_card(card1, 0, 0)
        container.add_card(card2, 0, 4)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)
        assert len(sidebar._buttons) == 2

    def test_button_for_card(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card = BaseCard("Card 1", card_id="card_1")
        container.add_card(card, 0, 0)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)

        btn = sidebar._buttons["card_1"]
        assert btn.toolTip() == "Card 1"
        assert btn.text() == "C"

    def test_button_checked_state_matches_visibility(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card = BaseCard("Test", card_id="test_card")
        container.add_card(card, 0, 0)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)

        assert sidebar._buttons["test_card"].isChecked() is True
        container.hide_card("test_card")
        assert sidebar._buttons["test_card"].isChecked() is False

    def test_toggle_card_from_button(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card = BaseCard("Test", card_id="test_card")
        container.add_card(card, 0, 0)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)

        sidebar._buttons["test_card"].click()

        assert "test_card" not in container._cards
        assert "test_card" in container._hidden_cards

    def test_add_card_updates_buttons(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card1 = BaseCard("Card 1", card_id="card_1")
        container.add_card(card1, 0, 0)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)
        assert len(sidebar._buttons) == 1

        card2 = BaseCard("Card 2", card_id="card_2")
        container.add_card(card2, 0, 4)

        assert "card_2" in sidebar._buttons
        assert len(sidebar._buttons) == 2

    def test_remove_card_removes_button(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card1 = BaseCard("Card 1", card_id="card_1")
        card2 = BaseCard("Card 2", card_id="card_2")
        container.add_card(card1, 0, 0)
        container.add_card(card2, 0, 4)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)
        assert len(sidebar._buttons) == 2

        container.remove_card("card_1")

        assert "card_1" not in sidebar._buttons
        assert len(sidebar._buttons) == 1

    def test_visibility_changed_updates_button(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card = BaseCard("Test", card_id="test_card")
        container.add_card(card, 0, 0)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)

        container.toggle_card_visibility("test_card")
        assert sidebar._buttons["test_card"].isChecked() is False

        container.toggle_card_visibility("test_card")
        assert sidebar._buttons["test_card"].isChecked() is True

    def test_maximum_width(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card = BaseCard("Test", card_id="test_card")
        container.add_card(card, 0, 0)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)

        assert sidebar.maximumWidth() == 60
        assert sidebar.minimumWidth() == 40

    def test_buttons_are_checkable(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)
        card = BaseCard("Test", card_id="test_card")
        container.add_card(card, 0, 0)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)

        btn = sidebar._buttons["test_card"]
        assert btn.isCheckable() is True

    def test_toggle_button_exists(self, qtbot):
        container = DashboardContainer()
        qtbot.addWidget(container)

        sidebar = CardSidebar(container)
        qtbot.addWidget(sidebar)

        assert sidebar._toggle_btn is not None
        assert sidebar._toggle_btn.objectName() == "sidebarToggle"