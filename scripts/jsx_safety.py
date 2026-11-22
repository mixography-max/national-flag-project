"""Helpers for embedding data in generated Illustrator ExtendScript (JSX).

Values such as file paths and Pantone names come from data files in the
repository, so they must never be spliced into JSX source as raw text.
"""

import json
import re

# Country codes as used for file stems, e.g. "JP", "PY_reverse", "PE_state".
_SAFE_CODE = re.compile(r"[A-Z]{2}(?:_[A-Za-z0-9]+)*")


def js_str(value) -> str:
    """Return ``value`` as a JavaScript string literal (quotes included).

    ``ensure_ascii`` keeps U+2028/U+2029 escaped, which ES3 would otherwise
    treat as line terminators inside a string literal.
    """
    return json.dumps(str(value), ensure_ascii=True)


def is_safe_code(code: str) -> bool:
    return isinstance(code, str) and _SAFE_CODE.fullmatch(code) is not None


def filter_safe_codes(codes):
    """Drop codes that are not plain country codes, reporting each one."""
    safe = []
    for code in codes:
        if is_safe_code(code):
            safe.append(code)
        else:
            print(f"⚠️ Ignoring invalid country code: {code!r}")
    return safe
