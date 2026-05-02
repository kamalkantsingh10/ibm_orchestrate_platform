"""Cross-language parity test for confidence thresholds — Story 3.3 / AC #7.

The TS file at ``apps/cockpit-ui/src/lib/confidence.ts`` is hand-mirrored
from the Python source. This test reads the TS file as text, regex-extracts
each ``{ band, min }`` row, and asserts the numeric thresholds match the
Python ``THRESHOLDS`` table by ``band.name``.

If this test fails, exactly one of the two files drifted; align them and
re-run.
"""

from __future__ import annotations

import re
from pathlib import Path

from contracts.confidence import THRESHOLDS

_TS_PATH = Path(__file__).resolve().parents[3] / "apps/cockpit-ui/src/lib/confidence.ts"

_ROW_RE = re.compile(
    r"\{\s*band:\s*ConfidenceBand\.(?P<band>\w+),\s*min:\s*(?P<min>[\d.]+)\s*\}",
)


def test_thresholds_match_typescript_mirror() -> None:
    assert _TS_PATH.exists(), f"TS mirror missing: {_TS_PATH}"
    text = _TS_PATH.read_text()
    rows = _ROW_RE.findall(text)
    assert rows, f"could not parse threshold rows from {_TS_PATH}"

    ts_thresholds = {band: float(value) for band, value in rows}
    py_thresholds = {band.name: threshold for band, threshold in THRESHOLDS}

    assert ts_thresholds == py_thresholds, (
        f"TS thresholds {ts_thresholds} do not match Python thresholds {py_thresholds}"
    )
