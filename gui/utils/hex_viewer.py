"""Hex dump viewer widget with byte-range highlighting and resizable splitter."""

from PySide6.QtWidgets import QWidget, QTextEdit, QSplitter, QVBoxLayout
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat
from PySide6.QtCore import Qt


class HexDumpWidget(QWidget):
    """A read-only hex dump viewer with a resizable splitter between hex and ASCII.

    Displays data as two panels:
      0000: 01 00 40 0B 00 21 00 1B  │  .@..!...
      0010: 01 32 00 08 00 01 00 00  │  .2......

    Supports highlight(byte_start, byte_end) to highlight a range
    of bytes.
    """

    BYTES_PER_LINE = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_bytes: bytes = b""
        self._hex_byte_to_pos: list[int] = []
        self._ascii_byte_to_pos: list[int] = []

        self._hex_edit = QTextEdit(self)
        self._hex_edit.setReadOnly(True)
        self._hex_edit.setFont(QFont("Consolas", 11))
        self._hex_edit.setStyleSheet(
            "background-color: #1E1E1E; color: #CCCCCC; border: none;"
        )
        self._hex_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._hex_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        self._ascii_edit = QTextEdit(self)
        self._ascii_edit.setReadOnly(True)
        self._ascii_edit.setFont(QFont("Consolas", 11))
        self._ascii_edit.setStyleSheet(
            "background-color: #26262A; color: #CCCCCC; border: none;"
        )
        self._ascii_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._ascii_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.addWidget(self._hex_edit)
        self._splitter.addWidget(self._ascii_edit)
        self._splitter.setChildrenCollapsible(True)
        self._splitter.setHandleWidth(4)
        self._splitter.setStyleSheet(
            "QSplitter::handle { background-color: #3E3E42; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._splitter)

        self._highlight_hex_format = QTextCharFormat()
        self._highlight_hex_format.setBackground(QColor("#FFD700"))
        self._highlight_hex_format.setForeground(QColor("#1E1E1E"))
        self._highlight_ascii_format = QTextCharFormat()
        self._highlight_ascii_format.setBackground(QColor("#569CD6"))
        self._highlight_ascii_format.setForeground(QColor("#1E1E1E"))
        self._alt_highlight_hex_format = QTextCharFormat()
        self._alt_highlight_hex_format.setBackground(QColor("#8B8000"))
        self._alt_highlight_hex_format.setForeground(QColor("#FFFFFF"))
        self._alt_highlight_ascii_format = QTextCharFormat()
        self._alt_highlight_ascii_format.setBackground(QColor("#3E6060"))
        self._alt_highlight_ascii_format.setForeground(QColor("#FFFFFF"))

        self.show_placeholder()

    def show_placeholder(self, text: str = "(no data)"):
        self._hex_edit.setPlainText(text)
        self._ascii_edit.setPlainText(text)
        self._raw_bytes = b""
        self._hex_byte_to_pos = []
        self._ascii_byte_to_pos = []

    def toPlainText(self) -> str:
        return self._hex_edit.toPlainText()

    def isReadOnly(self) -> bool:
        return True

    def set_hex_data(self, hex_str: str | None):
        """Set the hex string to display."""
        if not hex_str or not isinstance(hex_str, str):
            self.show_placeholder("(no data)")
            return

        try:
            self._raw_bytes = bytes.fromhex(hex_str)
        except (ValueError, AttributeError):
            self.show_placeholder("(invalid hex)")
            return

        self._hex_byte_to_pos = []
        self._ascii_byte_to_pos = []
        hex_lines = []
        ascii_lines = []
        raw = self._raw_bytes
        hex_doc_pos = 0
        ascii_doc_pos = 0

        for i in range(0, len(raw), self.BYTES_PER_LINE):
            chunk = raw[i:i + self.BYTES_PER_LINE]
            offset = f"{i:04X}: "
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            padding = " " * ((self.BYTES_PER_LINE - len(chunk)) * 3)

            ascii_part = ""
            for b in chunk:
                ch = chr(b) if 32 <= b < 127 else "."
                ascii_part += ch

            hex_line = f"{offset}{hex_part}{padding}"
            ascii_line = ascii_part
            hex_lines.append(hex_line)
            ascii_lines.append(ascii_line)

            for byte_index in range(len(chunk)):
                hex_pos = hex_doc_pos + len(offset) + byte_index * 3
                ascii_pos = ascii_doc_pos + byte_index
                self._hex_byte_to_pos.append(hex_pos)
                self._ascii_byte_to_pos.append(ascii_pos)

            hex_doc_pos += len(hex_line) + 1
            ascii_doc_pos += len(ascii_line) + 1

        self._hex_edit.setPlainText("\n".join(hex_lines))
        self._ascii_edit.setPlainText("\n".join(ascii_lines))

    def highlight(self, byte_start: int, byte_end: int, alt: bool = False):
        """Highlight a range of bytes in both hex and ASCII panels."""
        hex_fmt = self._alt_highlight_hex_format if alt else self._highlight_hex_format
        ascii_fmt = self._alt_highlight_ascii_format if alt else self._highlight_ascii_format

        if byte_start < 0 or byte_end >= len(self._raw_bytes):
            return
        if byte_start > byte_end:
            byte_start, byte_end = byte_end, byte_start

        for byte_idx in range(byte_start, byte_end + 1):
            if byte_idx < len(self._hex_byte_to_pos):
                cursor = self._hex_edit.textCursor()
                cursor.setPosition(self._hex_byte_to_pos[byte_idx])
                cursor.movePosition(QTextCursor.MoveOperation.Right,
                                    QTextCursor.MoveMode.KeepAnchor, 2)
                cursor.mergeCharFormat(hex_fmt)

            if byte_idx < len(self._ascii_byte_to_pos):
                cursor = self._ascii_edit.textCursor()
                cursor.setPosition(self._ascii_byte_to_pos[byte_idx])
                cursor.movePosition(QTextCursor.MoveOperation.Right,
                                    QTextCursor.MoveMode.KeepAnchor, 1)
                cursor.mergeCharFormat(ascii_fmt)

    def clear_highlight(self):
        """Remove all highlights by re-setting the plain text."""
        self._hex_edit.setPlainText(self._hex_edit.toPlainText())
        self._ascii_edit.setPlainText(self._ascii_edit.toPlainText())
