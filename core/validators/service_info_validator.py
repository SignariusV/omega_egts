"""Валидатор Service Info negotiation (ТЗ п. 2.3.1 шаг 11)."""

from __future__ import annotations

from core.validators.auth_validator import AuthValidationResult


class ServiceInfoValidator:
    """Валидация Service Info negotiation.

    ПО ИИОЭР поддерживает только базовую услугу EGTS_ECALL_SERVICE (ST=10).
    Все остальные сервисы запрещены (ТЗ п. 1.6).
    """

    ALLOWED_SERVICE_TYPE = 10  # EGTS_ECALL_SERVICE

    def validate_request(self, service_type: int) -> AuthValidationResult:
        """Проверить, запрашивает ли УВ разрешённый сервис."""
        if service_type == self.ALLOWED_SERVICE_TYPE:
            return AuthValidationResult(passed=True, reasons=[])
        return AuthValidationResult(
            passed=False,
            reasons=[f"Сервис ST={service_type} не поддерживается (разрешён только ST={self.ALLOWED_SERVICE_TYPE})"],
        )

    def build_accept_response(self) -> dict:
        """Построить ответ: сервис ST=10 доступен."""
        return {"st": self.ALLOWED_SERVICE_TYPE, "sst": 0, "srvp": 0, "srva": False, "srvrp": 0}

    def build_reject_response(self, requested_type: int) -> dict:
        """Построить ответ: сервис недоступен."""
        return {"st": requested_type, "sst": 0, "srvp": 0x80, "srva": True, "srvrp": 0}
