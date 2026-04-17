from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OperationLogger:
    verbose: bool = False
    messages: list[str] = field(default_factory=list)

    def info(self, message: str) -> None:
        self.messages.append(message)

    def detail(self, message: str) -> None:
        if self.verbose:
            self.messages.append(message)

    def progress(self, current: int, total: int, message: str) -> None:
        if self.verbose:
            self.messages.append(f"[{current}/{total}] {message}")
