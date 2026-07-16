"""Marker-region engine for resilum:managed config sections."""

import re

# Lookahead (not \b): \b fires on the '-', so "ygg-public-listen" would
# also match a "ygg-public-listen-extra" marker.
_OPEN_RE_TMPL = r"^[ \t]*# >>> resilum:managed {tag}(?=[ \t]|$).*$"
_CLOSE_RE = re.compile(r"^[ \t]*# <<< resilum:managed\b.*$")


def replace_region(text, tag, body_lines):
    """Replace the lines between the <tag> markers with body_lines.

    Returns the new text, or None if the opening marker is absent.
    Raises ValueError if the region is opened but never closed.
    body_lines carry their own absolute indentation.
    """
    open_re = re.compile(_OPEN_RE_TMPL.format(tag=re.escape(tag)))
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if open_re.match(ln)), None)
    if start is None:
        return None
    end = next(
        (j for j in range(start + 1, len(lines)) if _CLOSE_RE.match(lines[j])),
        None,
    )
    if end is None:
        raise ValueError(f"unterminated resilum:managed region for {tag!r}")
    new = lines[: start + 1] + list(body_lines) + lines[end:]
    tail = "\n" if text.endswith("\n") else ""
    return "\n".join(new) + tail
