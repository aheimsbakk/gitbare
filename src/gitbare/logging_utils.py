from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO


@dataclass
class OperationLogger:
    verbose: bool = False
    stream: TextIO = sys.stderr

    def emit(self, message: str, *, verbose_only: bool) -> None:
        if verbose_only and not self.verbose:
            return
        print(message, file=self.stream, flush=True)

    def info(self, message: str) -> None:
        self.emit(message, verbose_only=False)

    def detail(self, message: str) -> None:
        self.emit(message, verbose_only=True)

    def progress(self, current: int, total: int, message: str) -> None:
        self.emit(f"[{current}/{total}] {message}", verbose_only=True)
