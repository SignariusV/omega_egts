# OMEGA_EGTS GUI
import logging
from PySide6.QtCore import QObject, Signal


class QLogHandler(QObject, logging.Handler):
    log_message = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        logging.Handler.__init__(self)

    def emit(self, record: logging.LogRecord):
        try:
            msg = {
                "level": record.levelname,
                "message": self.format(record),
                "timestamp": record.created,
            }
            self.log_message.emit(msg)
        except Exception:
            pass