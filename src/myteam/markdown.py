from __future__ import annotations

import re

_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE = re.compile(r"^ {0,3}(`+|~+)[ \t]*$")
_HEADING = re.compile(r"^( {0,3})(#+)(?=[ \t]|$)")


def increase_headers(content: str, offset: int = 1) -> str:
    """Increase ATX heading marker runs outside fenced code blocks."""
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    if type(offset) is not int:
        raise TypeError("offset must be an integer")
    if offset < 0:
        raise ValueError("offset must not be negative")
    if offset == 0:
        return content

    rendered: list[str] = []
    fence_marker: str | None = None
    fence_length = 0

    for line in content.splitlines(keepends=True):
        body = _line_body(line)

        if fence_marker is not None:
            closer = _FENCE_CLOSE.fullmatch(body)
            if (
                closer is not None
                and closer.group(1)[0] == fence_marker
                and len(closer.group(1)) >= fence_length
            ):
                fence_marker = None
                fence_length = 0
            rendered.append(line)
            continue

        opener = _FENCE_OPEN.fullmatch(body)
        if opener is not None and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
            fence_marker = opener.group(1)[0]
            fence_length = len(opener.group(1))
            rendered.append(line)
            continue

        heading = _HEADING.match(body)
        if heading is not None:
            marker_start = heading.start(2)
            line = f"{line[:marker_start]}{'#' * offset}{line[marker_start:]}"
        rendered.append(line)

    return "".join(rendered)


def _line_body(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith("\n"):
        return line[:-1]
    return line
