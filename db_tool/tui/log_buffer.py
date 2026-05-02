from collections import deque

_LOG_BUFFER: deque[tuple[int, str, str]] = deque(maxlen=1000)


def add_log(level: int, logger_name: str, formatted: str) -> None:
    _LOG_BUFFER.append((level, logger_name, formatted))


def get_all_logs() -> list[tuple[int, str, str]]:
    return list(_LOG_BUFFER)


def clear_logs() -> None:
    _LOG_BUFFER.clear()