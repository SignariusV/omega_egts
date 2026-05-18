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
    # Place card2 in a non-overlapping position
    container.add_card(card2, 0, 4)
    card1_id = card1.card_id

    original_pos = container._cards[card1_id]
    # Try to move card1 to where card2 is
    container.move_card(card1_id, 0, 4)
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


def test_resize_card_syncs_card_size(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    card_id = card.card_id
    container.add_card(card, 0, 0)
    assert card.grid_size == (4, 4)

    container.resize_card(card_id, 2, 3)
    assert container._cards[card_id] == (0, 0, 2, 3)
    assert card.grid_size == (2, 3)


def test_add_card_clamps_oversized(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Test")
    container.add_card(card, 5, 5, 10, 10)
    card_id = card.card_id
    assert card_id in container._cards
    row, col, row_span, col_span = container._cards[card_id]
    assert row_span <= 8
    assert col_span <= 8
    assert row + row_span <= 8
    assert col + col_span <= 8


def test_add_card_finds_free_spot_when_occupied(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card1 = BaseCard("Card1")
    card2 = BaseCard("Card2")
    container.add_card(card1, 0, 0)
    # card2 at (0,0) overlaps with card1, should find free spot
    container.add_card(card2, 0, 0)
    card2_id = card2.card_id
    assert card2_id in container._cards
    # card2 should NOT be at (0,0) since card1 is there
    r, c, rs, cs = container._cards[card2_id]
    assert not (r == 0 and c == 0)


def test_add_card_returns_no_space_when_full(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    # Fill the grid with 4 cards of 4x4
    c1 = BaseCard("C1")
    c2 = BaseCard("C2")
    c3 = BaseCard("C3")
    c4 = BaseCard("C4")
    container.add_card(c1, 0, 0)
    container.add_card(c2, 0, 4)
    container.add_card(c3, 4, 0)
    container.add_card(c4, 4, 4)
    # Grid is full, new card should not be added
    c5 = BaseCard("C5")
    container.add_card(c5, 0, 0)
    assert c5.card_id not in container._cards
    assert c5.card_id not in container._hidden_cards


def test_register_hidden_card(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Hidden")
    container.register_hidden_card(card)
    card_id = card.card_id
    assert card_id not in container._cards
    assert card_id in container._hidden_cards
    assert container.has_card(card_id) is True
    assert container.is_card_visible(card_id) is False
    assert card.isHidden() is True


def test_register_hidden_card_show(qtbot):
    container = DashboardContainer()
    qtbot.addWidget(container)
    card = BaseCard("Hidden")
    container.register_hidden_card(card)
    card_id = card.card_id

    container.show_card(card_id)
    assert card_id in container._cards
    assert card_id not in container._hidden_cards
    assert container.is_card_visible(card_id) is True