from typing import Any, Optional
import re

def extract_json_value(data: Any, path: str) -> Any:
    """
    Extracts a value from a nested dictionary or list using dot notation.
    Supports list indices (e.g. 'items.0.id').
    """
    keys = path.split('.')
    val = data
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        elif isinstance(val, list) and k.isdigit():
            try:
                val = val[int(k)]
            except IndexError:
                val = None
                break
        else:
            val = None
            break
    return val

def extract_regex_value(text: str, pattern: str) -> Optional[str]:
    """
    Extracts a value from text using a regex pattern.
    Returns the first group if present, otherwise the whole match.
    """
    if not text or not pattern:
        return None
    match = re.search(pattern, str(text))
    if match:
        return match.group(1) if match.groups() else match.group(0)
    return None
