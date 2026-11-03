"""Parse bounded, literal script text without fetching assets or creating media."""

import re
import unicodedata
from pathlib import Path

from preflight.schema import ScriptLine

MAX_SCRIPT_BYTES = 64 * 1024
MAX_SCRIPT_LINES = 1000
SCRIPT_SUFFIXES = {".txt", ".md"}
SCRIPT_TYPES = {"text/plain": ".txt", "text/markdown": ".md"}
PREFIX = re.compile(r"^\s*(VO|SUPER):[ \t]*", re.IGNORECASE)


class ScriptError(ValueError):
    """The message is a public error code and never contains submitted text."""


def parse_script(
    raw: bytes, *, max_bytes: int = MAX_SCRIPT_BYTES, max_lines: int = MAX_SCRIPT_LINES,
) -> tuple[ScriptLine, ...]:
    if len(raw) > max_bytes:
        raise ScriptError("script_too_large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ScriptError("invalid_script_encoding") from None
    if any(unicodedata.category(c) == "Cc" and c not in "\t\r\n" for c in text):
        raise ScriptError("invalid_script_content")
    physical = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # A final newline terminates the preceding physical line, not a new empty line.
    if physical and physical[-1] == "":
        physical.pop()
    if len(physical) > max_lines:
        raise ScriptError("script_too_many_lines")
    lines = []
    for number, raw_line in enumerate(physical, 1):
        hint = PREFIX.match(raw_line)
        content = raw_line[hint.end():] if hint else raw_line
        if not content.strip():
            continue
        channel = {"vo": "voiceover", "super": "super"}[hint[1].lower()] if hint else "plain"
        lines.append(ScriptLine(line_number=number, text=raw_line, channel=channel))
    if not lines:
        raise ScriptError("empty_script")
    return tuple(lines)


def script_bytes(path: Path, max_bytes: int = MAX_SCRIPT_BYTES) -> bytes:
    # Bound the read too, so a local CLI path cannot bypass upload limits.
    with path.open("rb") as source:
        return source.read(max_bytes + 1)


def read_script(path: Path, **limits) -> tuple[ScriptLine, ...]:
    return parse_script(script_bytes(path, limits.get("max_bytes", MAX_SCRIPT_BYTES)), **limits)
