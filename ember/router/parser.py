"""URL pattern parser: converts /users/{id:int} into regex + type converters."""
from __future__ import annotations
import re

# Supported type converters
CONVERTERS: dict[str, tuple[str, type]] = {
    "str": (r"[^/]+", str),
    "int": (r"\d+", int),
    "float": (r"\d+(?:\.\d+)?", float),
    "uuid": (r"[0-9a-fA-F-]{36}", str),
    "path": (r".+", str),
}

PARAM_RE = re.compile(r"\{(\w+)(?::(\w+))?\}")


def parse_pattern(pattern: str) -> tuple[re.Pattern, list[tuple[str, type]], bool]:
    """Parse a URL pattern into a compiled regex, param list, and dynamic flag.

    Returns:
        (compiled_regex, [(name, converter), ...], is_dynamic)
    """
    params: list[tuple[str, type]] = []
    is_dynamic = False
    regex = "^"

    pos = 0
    for match in PARAM_RE.finditer(pattern):
        is_dynamic = True
        start, end = match.span()
        regex += re.escape(pattern[pos:start])
        name = match.group(1)
        type_name = match.group(2) or "str"
        if type_name not in CONVERTERS:
            type_name = "str"
        pattern_str, converter = CONVERTERS[type_name]
        regex += f"(?P<{name}>{pattern_str})"
        params.append((name, converter))
        pos = end

    regex += re.escape(pattern[pos:]) + "$"
    return re.compile(regex), params, is_dynamic
