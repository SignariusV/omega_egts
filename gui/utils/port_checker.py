# OMEGA_EGTS GUI - Port checking utility
import socket
from typing import Optional


def is_port_available(host: str, port: int) -> tuple[bool, Optional[int]]:
    """
    Check if a port is available for binding.
    
    Returns:
        (is_available, pid_using_port)
        - is_available: True if port is free
        - pid_using_port: PID of process using the port (None if available)
    """
    # Try to bind to the port with SO_REUSEADDR
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Allow reuse to avoid "address already in use" from TIME_WAIT state
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        return True, None
    except OSError as e:
        # Port is in use - try to find which process
        pid = _find_process_using_port(port)
        return False, pid


def _find_process_using_port(port: int) -> Optional[int]:
    """Find PID of process using the given TCP port (Windows only)."""
    try:
        import subprocess
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5
        )
        lines = result.stdout.split("\n")
        for line in lines:
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    try:
                        return int(parts[-1])  # Last column is PID
                    except ValueError:
                        pass
    except Exception:
        pass
    return None


def get_error_message(host: str, port: int, pid: Optional[int] = None) -> str:
    """Generate a user-friendly error message."""
    msg = f"Порт {port} на адресе {host} уже используется!\n\n"
    
    if pid:
        msg += f"Процесс, занимающий порт: PID {pid}\n"
        msg += f"Для освобождения выполните: taskkill /F /PID {pid}\n\n"
    else:
        msg += "Не удалось определить процесс, занимающий порт.\n\n"
    
    msg += "Варианты решения:\n"
    msg += "1. Остановите сервер, если он уже запущен\n"
    msg += "2. Измените порт в Settings Card → General → TCP Port\n"
    msg += "3. Перезапустите приложение"
    
    return msg
