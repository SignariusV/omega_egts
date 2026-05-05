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
    card_id = card.card_id
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
    container.add_card(card, 0, 0)  # Adds with default grid_size (4, 4)
    card_id = card.card_id
    container.move_card(card_id, 1, 1)
    # Position changed, but grid_size (row_span, col_span) preserved
    assert container._cards[card_id] == (1, 1, 4, 4)


def test_hide_card(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    assert card_id in container._cards

    with qtbot.waitSignal(container.card_visibility_changed):
        container.hide_card(card_id)

    assert card_id not in container._cards
    assert card_id in container._hidden_cards


def test_show_card(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    container.hide_card(card_id)
    assert card_id in container._hidden_cards
    assert card_id not in container._cards

    with qtbot.waitSignal(container.card_visibility_changed):
        container.show_card(card_id)

    assert card_id in container._cards
    assert card_id not in container._hidden_cards


def test_show_hidden_card_emits_once(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    container.hide_card(card_id)

    emissions = []
    container.card_visibility_changed.connect(lambda cid, v: emissions.append((cid, v)))

    container.show_card(card_id)
    assert len(emissions) == 1
    assert emissions[0] == (card_id, True)


def test_hide_visible_card_emits_once(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)

    emissions = []
    container.card_visibility_changed.connect(lambda cid, v: emissions.append((cid, v)))

    container.hide_card(card_id)
    assert len(emissions) == 1
    assert emissions[0] == (card_id, False)


def test_show_card_no_emit_when_already_visible(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)

    emissions = []
    container.card_visibility_changed.connect(lambda cid, v: emissions.append((cid, v)))

    container.show_card(card_id)
    assert len(emissions) == 0


def test_hide_card_no_emit_when_already_hidden(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    container.hide_card(card_id)

    emissions = []
    container.card_visibility_changed.connect(lambda cid, v: emissions.append((cid, v)))

    container.hide_card(card_id)
    assert len(emissions) == 0


def test_toggle_card_visibility(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    assert card_id in container._cards

    with qtbot.waitSignal(container.card_visibility_changed):
        container.toggle_card_visibility(card_id)

    assert card_id not in container._cards
    assert card_id in container._hidden_cards

    with qtbot.waitSignal(container.card_visibility_changed):
        container.toggle_card_visibility(card_id)

    assert card_id in container._cards
    assert card_id not in container._hidden_cards


def test_resize_card(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    assert container._cards[card_id] == (0, 0, 4, 4)

    with qtbot.waitSignal(container.cards_changed):
        container.resize_card(card_id, 2, 3)

    assert container._cards[card_id] == (0, 0, 2, 3)


def test_move_card_invalid_position(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    original_pos = container._cards[card_id]

    container.move_card(card_id, 100, 100)
    assert container._cards[card_id] == original_pos


def test_move_card_to_occupied_area(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card1 = BaseCard("Card1")
    card2 = BaseCard("Card2")
    container.add_card(card1, 0, 0)
    container.add_card(card2, 2, 0)
    card1_id = card1.card_id

    original_pos = container._cards[card1_id]
    container.move_card(card1_id, 2, 0)
    assert container._cards[card1_id] == original_pos


def test_is_card_visible(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    assert container.is_card_visible(card_id) is True

    container.hide_card(card_id)
    assert container.is_card_visible(card_id) is False


def test_has_card(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    assert container.has_card(card_id) is True

    container.hide_card(card_id)
    assert container.has_card(card_id) is True

    container.remove_card(card_id)
    assert container.has_card(card_id) is False


def test_get_hidden_snapshot(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    container.hide_card(card_id)

    snapshot = container.get_hidden_snapshot()
    assert len(snapshot) == 1
    assert snapshot[0]["card_id"] == card_id


def test_apply_layout_snapshot(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    container.add_card(card, 0, 0)
    card_id = card.card_id

    snapshot = [{"card_id": card_id, "row": 2, "col": 2, "row_span": 2, "col_span": 2}]
    container.apply_layout_snapshot(snapshot)

    assert container._cards[card_id] == (2, 2, 2, 2)


def test_add_card_preserves_hidden_position(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id

    container.add_card(card, 0, 0)
    container.hide_card(card_id)
    assert card_id in container._hidden_cards
    assert container._hidden_cards[card_id] == (0, 0, 4, 4)

    container.add_card(card, 2, 2)
    assert card_id in container._cards
    assert container._cards[card_id][0] == 2
    assert container._cards[card_id][1] == 2