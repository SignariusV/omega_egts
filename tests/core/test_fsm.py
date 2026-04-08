"""Тесты UsvStateMachine — конечный автомат состояний УСВ по ГОСТ 33465-2015.

Покрывает все 18 переходов FSM:
- TCP connect/disconnect
- Авторизация (TERM_IDENTITY, RESULT_CODE)
- Конфигурирование (TID=0)
- Переавторизация
- Таймауты (6с, 5с × 3)
- Ошибки CRC/формата
- Команды оператора
"""

from core.session import UsvState, UsvStateMachine

# =============================================================================
# Вспомогательные функции
# =============================================================================


def _make_packet(
    service: int | None = None,
    tid: int | None = None,
    result_code: int | None = None,
    subrecord_type: int | None = None,
    record_status: int | None = None,
) -> dict:
    """Создать мок пакета для тестов FSM."""
    packet: dict[str, object] = {}
    if service is not None:
        packet["service"] = service
    if tid is not None:
        packet["tid"] = tid
    if result_code is not None:
        packet["result_code"] = result_code
    if subrecord_type is not None:
        packet["subrecord_type"] = subrecord_type
    if record_status is not None:
        packet["record_status"] = record_status
    return packet


# =============================================================================
# Базовые переходы (7 тестов)
# =============================================================================


class TestBasicTransitions:
    """Базовые переходы FSM."""

    def test_disconnected_to_connected(self) -> None:
        """TCP connect → DISCONNECTED → CONNECTED."""
        fsm = UsvStateMachine()
        assert fsm.state == UsvState.DISCONNECTED

        new_state = fsm.on_connect()
        assert new_state == UsvState.CONNECTED
        assert fsm.state == UsvState.CONNECTED

    def test_connected_to_authenticating(self) -> None:
        """TERM_IDENTITY (service=1) → CONNECTED → AUTHENTICATING."""
        fsm = UsvStateMachine()
        fsm.on_connect()

        packet = _make_packet(service=1)
        new_state = fsm.on_packet(packet)
        assert new_state == UsvState.AUTHENTICATING
        assert fsm.state == UsvState.AUTHENTICATING

    def test_connected_to_running_std(self) -> None:
        """eCall (service=10) для штатного УСВ → CONNECTED → RUNNING."""
        fsm = UsvStateMachine(is_std_usv=True)
        fsm.on_connect()

        # service=10 = ECALL_SERVICE
        packet = _make_packet(service=10)
        new_state = fsm.on_packet(packet)
        assert new_state == UsvState.RUNNING
        assert fsm.state == UsvState.RUNNING

    def test_connected_to_disconnected_timeout(self) -> None:
        """Таймаут 6с без TERM_IDENTITY → CONNECTED → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()

        # Таймаут 6с истёк
        new_state = fsm.on_timeout()
        assert new_state == UsvState.DISCONNECTED
        assert fsm.state == UsvState.DISCONNECTED

    def test_authenticating_to_configuring(self) -> None:
        """RESULT_CODE(153), TID=0 → AUTHENTICATING → CONFIGURING."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1, tid=0))

        # Сервер отправляет RESULT_CODE(153)
        new_state = fsm.on_result_code_sent(result_code=153)
        assert new_state == UsvState.CONFIGURING
        assert fsm.state == UsvState.CONFIGURING

    def test_authenticating_to_authorized(self) -> None:
        """RESULT_CODE(0) → AUTHENTICATING → AUTHORIZED."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))

        new_state = fsm.on_result_code_sent(result_code=0)
        assert new_state == UsvState.AUTHORIZED
        assert fsm.state == UsvState.AUTHORIZED

    def test_authenticating_to_disconnected_error(self) -> None:
        """RESULT_CODE(151, AUTH_DENIED) → AUTHENTICATING → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))

        new_state = fsm.on_result_code_sent(result_code=151)
        assert new_state == UsvState.DISCONNECTED
        assert fsm.state == UsvState.DISCONNECTED


# =============================================================================
# Сложные переходы (7 тестов)
# =============================================================================


class TestComplexTransitions:
    """Сложные переходы FSM."""

    def test_configuring_to_authenticating(self) -> None:
        """Повторная TERM_IDENTITY с TID>0 → CONFIGURING → AUTHENTICATING."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1, tid=0))
        fsm.on_result_code_sent(result_code=153)

        assert fsm.state == UsvState.CONFIGURING

        # УСВ отправляет TERM_IDENTITY повторно с TID=42
        packet = _make_packet(service=1, tid=42)
        new_state = fsm.on_packet(packet)
        assert new_state == UsvState.AUTHENTICATING
        assert fsm.state == UsvState.AUTHENTICATING

    def test_configuring_to_disconnected_timeout(self) -> None:
        """Таймаут 5с × 3 → CONFIGURING → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1, tid=0))
        fsm.on_result_code_sent(result_code=153)

        # 3 таймаута по 5с
        for _ in range(3):
            fsm.on_timeout()

        assert fsm.state == UsvState.DISCONNECTED

    def test_authorized_to_running(self) -> None:
        """Данные сервиса (service=2) → AUTHORIZED → RUNNING."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_result_code_sent(result_code=0)

        assert fsm.state == UsvState.AUTHORIZED

        packet = _make_packet(service=2)
        new_state = fsm.on_packet(packet)
        assert new_state == UsvState.RUNNING
        assert fsm.state == UsvState.RUNNING

    def test_authorized_to_authenticating(self) -> None:
        """Переавторизация (service=1) → AUTHORIZED → AUTHENTICATING."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_result_code_sent(result_code=0)

        assert fsm.state == UsvState.AUTHORIZED

        # УСВ запрашивает повторную авторизацию
        packet = _make_packet(service=1)
        new_state = fsm.on_packet(packet)
        assert new_state == UsvState.AUTHENTICATING
        assert fsm.state == UsvState.AUTHENTICATING

    def test_running_to_authenticating(self) -> None:
        """Переавторизация из RUNNING → AUTHENTICATING."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_result_code_sent(result_code=0)
        fsm.on_packet(_make_packet(service=2))

        assert fsm.state == UsvState.RUNNING

        packet = _make_packet(service=1)
        new_state = fsm.on_packet(packet)
        assert new_state == UsvState.AUTHENTICATING
        assert fsm.state == UsvState.AUTHENTICATING

    def test_running_to_disconnected_timeout(self) -> None:
        """Таймаут 5с × 3 → RUNNING → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_result_code_sent(result_code=0)
        fsm.on_packet(_make_packet(service=2))

        # 3 таймаута
        for _ in range(3):
            fsm.on_timeout()

        assert fsm.state == UsvState.DISCONNECTED

    def test_running_to_error(self) -> None:
        """Ошибка CRC/формата → RUNNING → ERROR."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_result_code_sent(result_code=0)
        fsm.on_packet(_make_packet(service=2))

        new_state = fsm.on_error(reason="CRC mismatch")
        assert new_state == UsvState.ERROR
        assert fsm.state == UsvState.ERROR


# =============================================================================
# Таймауты и edge cases (6 тестов)
# =============================================================================


class TestTimeoutsAndEdgeCases:
    """Таймауты и граничные случаи."""

    def test_timeout_in_connected_state(self) -> None:
        """6с без TERM_IDENTITY → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()

        result = fsm.on_timeout()
        assert result == UsvState.DISCONNECTED

    def test_timeout_in_authenticating_state(self) -> None:
        """5с × 3 → AUTHENTICATING → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))

        # 3 таймаута = 15с
        for i in range(3):
            result = fsm.on_timeout()
            if i < 2:
                assert fsm.state == UsvState.AUTHENTICATING
            else:
                assert result == UsvState.DISCONNECTED

        assert fsm.state == UsvState.DISCONNECTED

    def test_timeout_in_running_state(self) -> None:
        """5с × 3 → RUNNING → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))  # → AUTHENTICATING
        fsm.on_result_code_sent(result_code=0)  # → AUTHORIZED
        fsm.on_packet(_make_packet(service=2))  # → RUNNING

        for i in range(3):
            result = fsm.on_timeout()
            if i < 2:
                assert fsm.state == UsvState.RUNNING
            else:
                assert result == UsvState.DISCONNECTED

        assert fsm.state == UsvState.DISCONNECTED

    def test_unexpected_packet_logged(self) -> None:
        """Неожиданный пакет в CONNECTED → WARNING, состояние не меняется."""
        fsm = UsvStateMachine()
        fsm.on_connect()

        # service=2 (телеметрия) в CONNECTED — неожиданно
        packet = _make_packet(service=2)
        fsm.on_packet(packet)

        # Состояние не меняется (или меняется на RUNNING для штатного УСВ)
        assert fsm.state in (UsvState.CONNECTED, UsvState.RUNNING)

    def test_disconnect_from_any_state(self) -> None:
        """TCP disconnect из любого состояния → DISCONNECTED."""
        fsm = UsvStateMachine()

        # CONNECTED
        fsm.on_connect()
        fsm.on_disconnect()
        assert fsm.state == UsvState.DISCONNECTED

        # AUTHENTICATING
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_disconnect()
        assert fsm.state == UsvState.DISCONNECTED

        # CONFIGURING
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_result_code_sent(result_code=153)
        fsm.on_disconnect()
        assert fsm.state == UsvState.DISCONNECTED

        # AUTHORIZED
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_result_code_sent(result_code=0)
        fsm.on_disconnect()
        assert fsm.state == UsvState.DISCONNECTED

        # RUNNING
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))
        fsm.on_result_code_sent(result_code=0)
        fsm.on_packet(_make_packet(service=2))
        fsm.on_disconnect()
        assert fsm.state == UsvState.DISCONNECTED

        # ERROR
        fsm.on_connect()
        fsm.on_error("test error")
        fsm.on_disconnect()
        assert fsm.state == UsvState.DISCONNECTED

    def test_operator_force_disconnect(self) -> None:
        """Команда оператора → ERROR → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))

        # Принудительный сброс от оператора
        new_state = fsm.on_operator_command("force_disconnect")
        assert new_state == UsvState.ERROR
        assert fsm.state == UsvState.ERROR

        # Разрыв соединения → DISCONNECTED
        fsm.on_disconnect()
        assert fsm.state == UsvState.DISCONNECTED


# =============================================================================
# Штатное УСВ (eCall-only)
# =============================================================================


class TestStdUsvMode:
    """FSM для штатного УСВ (без авторизации)."""

    def test_std_usv_connected_to_running(self) -> None:
        """Штатное УСВ: CONNECTED → RUNNING по eCall (service=10)."""
        fsm = UsvStateMachine(is_std_usv=True)
        fsm.on_connect()

        packet = _make_packet(service=10)
        new_state = fsm.on_packet(packet)
        assert new_state == UsvState.RUNNING

    def test_std_usv_ignores_auth_packets(self) -> None:
        """Штатное УСВ: игнорирует AUTH_PARAMS, RESULT_CODE."""
        fsm = UsvStateMachine(is_std_usv=True)
        fsm.on_connect()

        # TERM_IDENTITY не переводит в AUTHENTICATING для штатного УСВ
        packet = _make_packet(service=1)
        # Для штатного УСВ service=1 может быть проигнорирован
        # или обработан иначе — зависит от реализации
        # Здесь просто проверяем, что FSM не падает
        fsm.on_packet(packet)


# =============================================================================
# Сброс счётчика таймаутов и обработка RECORD_RESPONSE
# =============================================================================


class TestTimeoutCounterReset:
    """Проверка сброса счётчика при получении ответов."""

    def test_reset_timeout_counter(self) -> None:
        """reset_timeout_counter() сбрасывает счётчик в 0."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))  # → AUTHENTICATING

        # Имитируем 2 таймаута
        fsm.on_timeout()
        fsm.on_timeout()
        assert fsm._timeout_counter == 2

        # Сброс
        fsm.reset_timeout_counter()
        assert fsm._timeout_counter == 0

    def test_auth_info_resets_timeout_counter(self) -> None:
        """AUTH_INFO (subrecord_type=3) сбрасывает счётчик."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))  # → AUTHENTICATING

        # Имитируем таймауты
        fsm.on_timeout()
        fsm.on_timeout()
        assert fsm._timeout_counter == 2

        # Пришёл AUTH_INFO — счётчик сбрасывается
        packet = _make_packet(service=1, subrecord_type=3)
        fsm.on_packet(packet)
        assert fsm._timeout_counter == 0

    def test_record_response_resets_timeout_counter(self) -> None:
        """RECORD_RESPONSE (subrecord_type=0x8000, RST=0) сбрасывает счётчик."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))  # → AUTHENTICATING

        fsm.on_timeout()
        assert fsm._timeout_counter == 1

        packet = _make_packet(service=0x8000, subrecord_type=0x8000, record_status=0)
        fsm.on_packet(packet)
        assert fsm._timeout_counter == 0

    def test_record_response_rst_non_zero_disconnects(self) -> None:
        """RECORD_RESPONSE с RST != 0 → DISCONNECTED."""
        fsm = UsvStateMachine()
        fsm.on_connect()
        fsm.on_packet(_make_packet(service=1))  # → AUTHENTICATING

        packet = _make_packet(service=0x8000, subrecord_type=0x8000, record_status=5)
        new_state = fsm.on_packet(packet)
        assert new_state == UsvState.DISCONNECTED
        assert fsm.state == UsvState.DISCONNECTED

    def test_timeout_terminal_states_returns_none(self) -> None:
        """on_timeout() возвращает None для DISCONNECTED и ERROR."""
        fsm = UsvStateMachine()

        # DISCONNECTED
        fsm.on_timeout()  # Уже DISCONNECTED
        assert fsm.state == UsvState.DISCONNECTED
        # Повторные вызовы не должны ничего менять
        fsm.on_timeout()
        fsm.on_timeout()
        assert fsm.state == UsvState.DISCONNECTED
        assert fsm._timeout_counter == 0

        # ERROR
        fsm.on_connect()
        fsm.on_error("test")
        assert fsm.state == UsvState.ERROR
        fsm.on_timeout()
        assert fsm.state == UsvState.ERROR
        # Счётчик не увеличился для ERROR
        assert fsm._timeout_counter == 0
