from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger(__name__)

ERROR_ALREADY_EXISTS = 183
_MUTEX_NAME = "Local\\ytm-discord-status-singleton"


class SingleInstance:
    """Windows named mutex so only one updater runs."""

    def __init__(self, name: str = _MUTEX_NAME) -> None:
        self._name = name
        self._handle: int | None = None

    def acquire(self) -> bool:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        handle = kernel32.CreateMutexW(None, wintypes.BOOL(False), self._name)
        if not handle:
            log.warning("CreateMutex failed; continuing without single-instance lock")
            return True
        self._handle = int(handle)
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            self._handle = None
            return False
        return True

    def release(self) -> None:
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
