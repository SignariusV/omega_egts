# OMEGA_EGTS GUI
import pytest
from gui.dashboard.container import DashboardContainer
from gui.dashboard.card_base import BaseCard


def test_add_card(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test Card")
    container.add_card(card, 0, 0)
    assert len(container._cards) == 1
    assert container._grid.count() == 1


def test_add_card_with_spans(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test Card")
    container.add_card(card, 0, 0, 2, 1)
    snapshot = container.get_layout_snapshot()
    assert snapshot[0]["row_span"] == 2
    assert snapshot[0]["col_span"] == 1


def test_remove_card(qtbot):
    container = DashboardContainer()
    card = BaseCard("Test Card")
    container.add_card(card, 0, 0)
    card_id = id(card)
    container.remove_card(card_id)
    assert len(container._cards) == 0


def test_layout_snapshot(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card1 = BaseCard("Card1")
    card2 = BaseCard("Card2")
    container.add_card(card1, 0, 0)
    container.add_card(card2, 1, 0)
    snapshot = container.get_layout_snapshot()
    assert len(snapshot) == 2


def test_cards_changed_signal(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    with qtbot.waitSignal(container.cards_changed):
        container.add_card(card, 0, 0)


def test_move_card(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    container.add_card(card, 0, 0)
    card_id = id(card)
    container.move_card(card_id, 1, 1)
    assert container._cards[card_id] == (1, 1, 1, 1)