from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class ConsoleMessage:
    message_type: str
    text: str
    source_name: str = ""
    source_key: str = ""
    channel: Optional[int] = None


class Console:
    def __init__(self, *, echo_stdout: bool = True):
        self.echo_stdout = echo_stdout
        self.messages: List[ConsoleMessage] = []
        self.listeners: List[Callable[[ConsoleMessage], None]] = []

    def emit(
        self,
        message_type: str,
        text: str,
        *,
        source_name: str = "",
        source_key: str = "",
        channel: Optional[int] = None,
        stdout_text: Optional[str] = None,
    ) -> ConsoleMessage:
        message = ConsoleMessage(
            message_type=message_type,
            text=text,
            source_name=source_name,
            source_key=source_key,
            channel=channel,
        )
        self.messages.append(message)
        if self.echo_stdout:
            print(stdout_text if stdout_text is not None else self.format_for_stdout(message))
        for listener in list(self.listeners):
            listener(message)
        return message

    def add_listener(self, listener: Callable[[ConsoleMessage], None]):
        self.listeners.append(listener)

    def remove_listener(self, listener: Callable[[ConsoleMessage], None]):
        if listener in self.listeners:
            self.listeners.remove(listener)

    @staticmethod
    def format_for_stdout(message: ConsoleMessage) -> str:
        if message.message_type in {"say", "whisper", "shout", "regionsay", "im"}:
            channel = message.channel if message.channel is not None else 0
            source = f" {message.source_name}" if message.source_name else ""
            return f"CHAT [Channel {channel}]{source}: {message.text}"
        if message.message_type == "ownersay":
            return f"OWNER_SAY: {message.text}"
        if message.message_type == "stub":
            return message.text
        return f"{message.message_type.upper()}: {message.text}"


def default_console() -> Console:
    return Console()
