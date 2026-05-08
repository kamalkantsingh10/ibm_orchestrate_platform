"""Citation parser for Cockpit Chat agent replies — Story 6.8 / AC #10.

Extracts every `led_<26-char Crockford-Base32>` substring from a chat
reply. Mirror of the TS-side `parseCitations` helper.
"""

from __future__ import annotations

import re

_LEDGER_RE = re.compile(r"led_[0-9A-HJKMNP-TV-Z]{26}")


def parse_citations(text: str) -> list[str]:
    """Return the list of unique ledger entry IDs cited in `text`.

    Order is preserved on first occurrence; duplicates are collapsed.
    """
    seen: dict[str, None] = {}
    for match in _LEDGER_RE.finditer(text):
        seen.setdefault(match.group(0), None)
    return list(seen.keys())
