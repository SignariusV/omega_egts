"""Тесты для CredentialsRepository."""

import json
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.credentials import Credentials, CredentialsRepository


@pytest.fixture()
def sample_credentials() -> list[dict]:
    """Тестовые учётные данные."""
    return [
        {
            "imei": "351234567890123",
            "imsi": "250011234567890",
            "term_code": "TEST001",
            "auth_key": "key-001",
            "device_id": "USV-001",
            "description": "Test device 1",
        },
        {
            "imei": "351234567890124",
            "imsi": "250011234567891",
            "term_code": "TEST002",
            "auth_key": "key-002",
            "device_id": "USV-002",
            "description": "Test device 2",
        },
    ]


@pytest.fixture()
def credentials_file(tmp_path: Path, sample_credentials: list[dict]) -> Path:
    """Временный файл credentials.json."""
    cred_file = tmp_path / "credentials.json"
    cred_file.write_text(json.dumps({"credentials": sample_credentials}, ensure_ascii=False))
    return cred_file


class TestCredentialsDataclass:
    """Тесты dataclass Credentials."""

    def test_create_credentials(self) -> None:
        creds = Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001",
            auth_key="key-001",
            device_id="USV-001",
        )
        assert creds.imei == "351234567890123"
        assert creds.device_id == "USV-001"

    def test_credentials_with_optional_fields(self) -> None:
        creds = Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001",
            auth_key="key-001",
            device_id="USV-001",
            description="Optional description",
        )
        assert creds.description == "Optional description"

    def test_credentials_default_description(self) -> None:
        creds = Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001",
            auth_key="key-001",
            device_id="USV-001",
        )
        assert creds.description is None

    def test_credentials_to_dict(self) -> None:
        creds = Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001",
            auth_key="key-001",
            device_id="USV-001",
            description="Test",
        )
        d = creds.to_dict()
        assert d["imei"] == "351234567890123"
        assert d["description"] == "Test"


class TestCredentialsRepositoryLoad:
    """Тесты загрузки данных из JSON."""

    def test_load_from_file(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        assert len(repo.list_all()) == 2

    def test_load_empty_file(self, tmp_path: Path) -> None:
        cred_file = tmp_path / "empty.json"
        cred_file.write_text(json.dumps({"credentials": []}))
        repo = CredentialsRepository(cred_file)
        assert len(repo.list_all()) == 0

    def test_load_missing_file(self, tmp_path: Path) -> None:
        cred_file = tmp_path / "nonexistent.json"
        repo = CredentialsRepository(cred_file)
        assert len(repo.list_all()) == 0

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        cred_file = tmp_path / "invalid.json"
        cred_file.write_text("not json")
        repo = CredentialsRepository(cred_file)
        assert len(repo.list_all()) == 0


class TestCredentialsRepositoryFind:
    """Тесты поиска учётных данных."""

    def test_find_by_imei(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        creds = repo.find_by_imei("351234567890123")
        assert creds is not None
        assert creds.device_id == "USV-001"
        assert creds.term_code == "TEST001"

    def test_find_by_imei_not_found(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        creds = repo.find_by_imei("999999999999999")
        assert creds is None

    def test_get_by_device_id(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        creds = repo.get("USV-002")
        assert creds is not None
        assert creds.imei == "351234567890124"

    def test_get_not_found(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        creds = repo.get("NONEXISTENT")
        assert creds is None


class TestCredentialsRepositorySave:
    """Тесты сохранения учётных данных."""

    def test_save_new_credentials(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        new_creds = Credentials(
            imei="351234567890125",
            imsi="250011234567892",
            term_code="TEST003",
            auth_key="key-003",
            device_id="USV-003",
        )
        repo.save(new_creds)

        # Проверяем, что данные сохранены
        saved = repo.get("USV-003")
        assert saved is not None
        assert saved.imei == "351234567890125"

        # Проверяем, что файл обновлён
        with open(credentials_file) as f:
            data = json.load(f)
        assert len(data["credentials"]) == 3

    def test_update_existing_credentials(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        updated = Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001-UPDATED",
            auth_key="key-001-updated",
            device_id="USV-001",
        )
        repo.save(updated)

        saved = repo.get("USV-001")
        assert saved is not None
        assert saved.term_code == "TEST001-UPDATED"
        assert saved.auth_key == "key-001-updated"

    def test_save_persists_to_file(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        new_creds = Credentials(
            imei="351234567890126",
            imsi="250011234567893",
            term_code="TEST004",
            auth_key="key-004",
            device_id="USV-004",
            description="Saved device",
        )
        repo.save(new_creds)

        # Перезагружаем репозиторий и проверяем
        repo2 = CredentialsRepository(credentials_file)
        saved = repo2.get("USV-004")
        assert saved is not None
        assert saved.description == "Saved device"

    def test_save_uses_device_id_as_key(self, credentials_file: Path) -> None:
        """save() использует creds.device_id как ключ словаря."""
        repo = CredentialsRepository(credentials_file)
        new_creds = Credentials(
            imei="351234567890125",
            imsi="250011234567892",
            term_code="TEST003",
            auth_key="key-003",
            device_id="USV-003",
        )
        repo.save(new_creds)

        all_creds = repo.list_all()
        assert "USV-003" in all_creds

    def test_save_without_device_id_uses_imei(self, credentials_file: Path) -> None:
        """Если device_id=None, ключом становится IMEI."""
        repo = CredentialsRepository(credentials_file)
        new_creds = Credentials(
            imei="351234567890128",
            imsi="250011234567895",
            term_code="TEST006",
            auth_key="key-006",
            device_id="",  # Пустой device_id → falsy
        )
        repo.save(new_creds)

        all_creds = repo.list_all()
        assert "351234567890128" in all_creds


class TestCredentialsRepositoryListAll:
    """Тесты list_all."""

    def test_list_all_returns_dict(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        all_creds = repo.list_all()
        assert isinstance(all_creds, dict)
        assert "USV-001" in all_creds
        assert "USV-002" in all_creds

    def test_list_all_after_save(self, credentials_file: Path) -> None:
        repo = CredentialsRepository(credentials_file)
        new_creds = Credentials(
            imei="351234567890125",
            imsi="250011234567892",
            term_code="TEST003",
            auth_key="key-003",
            device_id="USV-003",
        )
        repo.save(new_creds)

        all_creds = repo.list_all()
        assert len(all_creds) == 3


class TestCredentialsRepositorySecureFile:
    """Тесты защиты файла учётных данных."""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="chmod не работает на Windows"
    )
    def test_secure_file_on_linux(self, tmp_path: Path) -> None:
        cred_file = tmp_path / "credentials.json"
        cred_file.write_text(json.dumps({"credentials": []}))

        with patch.object(sys, "platform", "linux"):
            CredentialsRepository(cred_file)
            # Проверяем, что права установлены на 0o600 (384 = 256 + 128)
            mode = cred_file.stat().st_mode & 0o777
            assert mode == stat.S_IRUSR | stat.S_IWUSR

    def test_secure_file_on_windows_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """На Windows логируется рекомендация ограничить ACL."""
        cred_file = tmp_path / "credentials.json"
        cred_file.write_text(json.dumps({"credentials": []}))

        with patch.object(sys, "platform", "win32"):
            CredentialsRepository(cred_file)

        assert "restrict ACL" in caplog.text

    @patch("os.chmod")
    def test_secure_file_handles_permission_error(
        self, mock_chmod: MagicMock, tmp_path: Path
    ) -> None:
        mock_chmod.side_effect = PermissionError("Access denied")
        cred_file = tmp_path / "credentials.json"
        cred_file.write_text(json.dumps({"credentials": []}))

        with patch.object(sys, "platform", "linux"):
            # Не должно выбрасывать исключение
            repo = CredentialsRepository(cred_file)
            assert len(repo.list_all()) == 0


class TestCredentialsRepositoryEdgeCases:
    """Тесты граничных случаев."""

    def test_load_credentials_without_device_id(self, tmp_path: Path) -> None:
        """Учётные данные без device_id используют IMEI как ключ."""
        cred_file = tmp_path / "credentials.json"
        data = {
            "credentials": [
                {
                    "imei": "351234567890123",
                    "imsi": "250011234567890",
                    "term_code": "TEST001",
                    "auth_key": "key-001",
                }
            ]
        }
        cred_file.write_text(json.dumps(data))

        repo = CredentialsRepository(cred_file)
        all_creds = repo.list_all()
        # device_id отсутствует → используется IMEI как ключ
        assert "351234567890123" in all_creds

    def test_load_credentials_with_extra_fields(self, tmp_path: Path) -> None:
        """Лишние поля в JSON игнорируются."""
        cred_file = tmp_path / "credentials.json"
        data = {
            "credentials": [
                {
                    "imei": "351234567890123",
                    "imsi": "250011234567890",
                    "term_code": "TEST001",
                    "auth_key": "key-001",
                    "device_id": "USV-001",
                    "unknown_field": "ignored",
                }
            ]
        }
        cred_file.write_text(json.dumps(data))

        repo = CredentialsRepository(cred_file)
        creds = repo.find_by_imei("351234567890123")
        assert creds is not None
        assert creds.device_id == "USV-001"

    def test_save_with_none_description(self, credentials_file: Path) -> None:
        """description=None не должен вызывать проблем."""
        repo = CredentialsRepository(credentials_file)
        new_creds = Credentials(
            imei="351234567890127",
            imsi="250011234567894",
            term_code="TEST005",
            auth_key="key-005",
            device_id="USV-005",
        )
        repo.save(new_creds)
        saved = repo.get("USV-005")
        assert saved is not None
        assert saved.description is None
