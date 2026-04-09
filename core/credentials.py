"""Хранилище учётных данных устройств."""

import json
import logging
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Credentials:
    """Учётные данные одного устройства УСВ."""

    imei: str
    imsi: str
    term_code: str
    auth_key: str
    device_id: str
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        result: dict[str, Any] = {
            "imei": self.imei,
            "imsi": self.imsi,
            "term_code": self.term_code,
            "auth_key": self.auth_key,
            "device_id": self.device_id,
        }
        if self.description is not None:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Credentials":
        """Создание из словаря."""
        return cls(
            imei=data["imei"],
            imsi=data["imsi"],
            term_code=data["term_code"],
            auth_key=data["auth_key"],
            device_id=data.get("device_id", data["imei"]),
            description=data.get("description"),
        )


class CredentialsRepository:
    """JSON-хранилище учётных данных с защитой файла.

    Поддерживает поиск по IMEI и device_id, сохранение новых данных
    и автоматическую защиту файла (chmod 600 на Linux/macOS,
    attrib +h на Windows).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._creds: dict[str, Credentials] = {}
        self._load()
        self._secure_file()

    # ------------------------------------------------------------------
    # Загрузка / сохранение
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Загрузить учётные данные из JSON-файла."""
        if not self._path.exists():
            logger.warning("Файл учётных данных не найден: %s", self._path)
            return

        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Ошибка чтения файла учётных данных: %s", exc)
            return

        for item in data.get("credentials", []):
            try:
                cred = Credentials.from_dict(item)
                # Ключ — device_id, если нет — используем IMEI
                key = cred.device_id or cred.imei
                self._creds[key] = cred
            except (KeyError, TypeError) as exc:
                logger.warning("Пропущена некорректная запись: %s", exc)

    def _save(self) -> None:
        """Сохранить учётные данные в JSON-файл."""
        items = [cred.to_dict() for cred in self._creds.values()]
        data = {"credentials": items}
        try:
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Ошибка записи файла учётных данных: %s", exc)
            raise

    def _secure_file(self) -> None:
        """Защитить файл учётных данных."""
        if not self._path.exists():
            return

        try:
            if sys.platform == "win32":
                # NOTE: attrib +h мешает последующей записи (PermissionError).
                # MVP: только предупреждение. Администратор должен вручную
                # ограничить ACL (Properties → Security → Advanced).
                logger.warning(
                    "Windows: restrict ACL for %s manually "
                    "(Properties → Security → Advanced)",
                    self._path,
                )
            else:
                os.chmod(self._path, stat.S_IRUSR | stat.S_IWUSR)
        except (OSError, PermissionError) as exc:
            logger.warning("Failed to secure credentials file: %s", exc)

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------

    def find_by_imei(self, imei: str) -> Credentials | None:
        """Найти учётные данные по IMEI."""
        for cred in self._creds.values():
            if cred.imei == imei:
                return cred
        return None

    def get(self, device_id: str) -> Credentials | None:
        """Найти учётные данные по device_id."""
        return self._creds.get(device_id)

    def save(self, creds: Credentials) -> None:
        """Сохранить или обновить учётные данные.

        Ключом является ``creds.device_id``. Если ``device_id``
        не задан — используется ``creds.imei``.
        """
        key = creds.device_id or creds.imei
        self._creds[key] = creds
        self._save()

    def list_all(self) -> dict[str, Credentials]:
        """Вернуть все учётные данные как словарь {device_id: Credentials}."""
        return dict(self._creds)
