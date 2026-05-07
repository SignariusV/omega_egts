# OMEGA_EGTS GUI
from pathlib import Path
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QScrollArea

from gui.dashboard.card_base import BaseCard


class CardSidebar(QWidget):
    """Sidebar with icon buttons to show/hide dashboard cards.
    
    Similar to IDE sidebars (PyCharm, VS Code), buttons reflect
    card visibility state and allow one-click toggle.
    """
    
    sidebar_hidden = Signal()
    sidebar_shown = Signal()
    
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        self._container = container
        self._buttons: dict[str, QToolButton] = {}
        
        self.setObjectName("cardSidebar")
        self.setMaximumWidth(60)
        self.setMinimumWidth(40)

        # Toggle button for hiding sidebar
        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("◀")
        self._toggle_btn.setToolTip("Hide sidebar")
        self._toggle_btn.setObjectName("sidebarToggle")
        self._toggle_btn.clicked.connect(self.hide)
        self._toggle_btn.setFixedSize(24, 24)
        
        # Scrollable area for buttons
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("cardSidebarScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._scroll.setStyleSheet("background-color: #1E1E1E; border: none;")
        self._scroll.viewport().setStyleSheet("background-color: #1E1E1E;")
        
        self._button_widget = QWidget()
        self._layout = QVBoxLayout(self._button_widget)
        self._layout.setContentsMargins(4, 8, 4, 8)
        self._layout.setSpacing(6)
        self._layout.addStretch()

        self._scroll.setWidget(self._button_widget)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._toggle_btn)
        main_layout.addWidget(self._scroll)

        self.setStyleSheet("""
            QToolTip {
                background-color: #2D2D30;
                color: #CCCCCC;
                border: 1px solid #3E3E42;
                padding: 4px 8px;
                border-radius: 3px;
            }
        """)

        # Subscribe to container changes
        container.cards_changed.connect(self._refresh_buttons)
        container.card_visibility_changed.connect(self._on_visibility_changed)
        
        # Initial population
        self._refresh_buttons()

    def showEvent(self, event):
        super().showEvent(event)
        self.sidebar_shown.emit()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.sidebar_hidden.emit()

    def _refresh_buttons(self):
        """Synchronize buttons with current set of cards."""
        existing_ids = set()
        for card in self._container.findChildren(BaseCard):
            cid = card.card_id
            existing_ids.add(cid)
            if cid not in self._buttons:
                self._add_button(cid, card)

        # Remove buttons for cards that no longer exist
        for cid in list(self._buttons.keys()):
            if cid not in existing_ids:
                self._remove_button(cid)

    def _add_button(self, card_id: str, card: BaseCard):
        """Add a button for the given card."""
        btn = QToolButton()
        
        # Use icon if available, otherwise use first letter of title
        icon_path = getattr(card, 'icon_path', None)
        icon_loaded = False
        
        if icon_path:
            # Преобразуем в абсолютный путь
            path_obj = Path(icon_path)
            if not path_obj.is_absolute():
                # sidebar.py: gui/dashboard/ -> 2 уровня вверх = gui/ -> ещё раз = OMEGA_EGTS/
                project_root = Path(__file__).resolve().parent.parent.parent
                abs_path_str = str(project_root / icon_path)
            else:
                abs_path_str = str(path_obj)
            
            abs_path = Path(abs_path_str)
            if abs_path.exists():
                icon = QIcon(str(abs_path))
                btn.setIcon(icon)
                btn.setIconSize(QSize(20, 20))
                icon_loaded = True
        
        # Если иконка не загружена — используем текст (первая буква заголовка)
        if not icon_loaded:
            btn.setText(card.title[:1].upper())
        
        # Стилизация: делаем фон светлым, чтобы чёрная SVG-иконка была видна
        if icon_loaded:
            btn.setStyleSheet("""
                QToolButton {
                    background-color: rgba(255,255,255, 50);
                    border: 1px solid rgba(255,255,255, 160);
                    border-radius: 4px;
                    padding: 2px;
                }
                QToolButton:checked {
                    background-color: rgba(255,255,255, 70);
                    border: 1px solid rgba(255,255,255, 230);
                }
                QToolButton:hover {
                    background-color: rgba(255,255,255, 90);
                    border: 1px solid rgba(255,255,255, 255);
                }
            """)
        else:
            btn.setStyleSheet("""
                QToolButton {
                    color: white;
                    background-color: rgba(255,255,255, 50);
                    border: 1px solid rgba(255,255,255, 160);
                    border-radius: 4px;
                }
                QToolButton:checked {
                    background-color: rgba(255,255,255, 70);
                    border: 1px solid rgba(255,255,255, 230);
                }
                QToolButton:hover {
                    background-color: rgba(255,255,255, 90);
                }
            """)
        
        btn.setToolTip(card.title)
        btn.setCheckable(True)
        btn.setChecked(not card.isHidden())
        btn.clicked.connect(lambda checked, cid=card_id: self._on_button_clicked(cid))
        btn.setObjectName(f"sidebarBtn_{card_id}")
        btn.setProperty("class", "SidebarButton")
        
        # Set button size
        btn.setFixedSize(36, 36)
        
        # Insert before the stretch
        self._layout.insertWidget(self._layout.count() - 1, btn)
        self._buttons[card_id] = btn

    def _remove_button(self, card_id: str):
        """Remove button for the given card ID."""
        if card_id in self._buttons:
            btn = self._buttons.pop(card_id)
            self._layout.removeWidget(btn)
            btn.deleteLater()

    def _on_button_clicked(self, card_id: str):
        """Handle button click - toggle card visibility."""
        self._container.toggle_card_visibility(card_id)

    def _on_visibility_changed(self, card_id: str, visible: bool):
        """Update button checked state when card visibility changes."""
        if card_id in self._buttons:
            self._buttons[card_id].setChecked(visible)
