"""Pinned Vora UBOGraph fixture for cockpit-api tests — Story 5.5.

Avoids cross-app coupling with the cockpit-ui __fixtures__ JSON file. The
shape is identical because both flow from Story 5.3's deterministic
construction; this Python module is the authoritative source for backend
tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import to_band
from contracts.provenance import Provenance, ProvenancedField
from contracts.ubo import UBOEdge, UBOEntityNode, UBOGraph, UBOPersonNode

VORA_ROOT_ID = "ubo_e_u67120mh2024ptc444789"
DEVANSH_ID = "ubo_p_09876543"
ROHAN_ID = "ubo_p_09876544"
FILING_ID = "ubo_p_09876545"
COASTAL_ID = "ubo_e_coastal_equity_partners_pte_ltd"
ANCHOR_ID = "ubo_e_anchor_trust_services_bvi"


def _pf(c: float) -> ProvenancedField[float]:
    return ProvenancedField(
        value=c,
        provenance=Provenance(
            source_agent="ubo_graph",
            source_system="mca_mock",
            confidence=c,
            confidence_band=to_band(c),
            evidence_ids=[],
            captured_at=datetime.now(UTC),
        ),
    )


def make_vora_graph() -> UBOGraph:
    return UBOGraph(
        case_id=VORA_CAPITAL_ID,
        root_entity_id=VORA_ROOT_ID,
        nodes=[
            UBOEntityNode(
                id=VORA_ROOT_ID,
                name="Vora Capital Holdings Pvt Ltd",
                cin="U67120MH2024PTC444789",
                country="IN",
            ),
            UBOPersonNode(id=DEVANSH_ID, name="Devansh Vora", din="09876543"),
            UBOPersonNode(id=ROHAN_ID, name="Rohan Mehta", din="09876544"),
            UBOPersonNode(id=FILING_ID, name="A K Filing Services", din="09876545"),
            UBOEntityNode(id=COASTAL_ID, name="Coastal Equity Partners Pte Ltd", country="SG", is_corporate=True),
            UBOEntityNode(id=ANCHOR_ID, name="Anchor Trust Services (BVI)", country="VG", is_corporate=True),
        ],
        edges=[
            UBOEdge(
                kind="director",
                from_id=DEVANSH_ID,
                to_id=VORA_ROOT_ID,
                designation="managing_director",
                confidence=_pf(0.95),
            ),
            UBOEdge(
                kind="director",
                from_id=ROHAN_ID,
                to_id=VORA_ROOT_ID,
                designation="director",
                confidence=_pf(0.95),
            ),
            UBOEdge(
                kind="director",
                from_id=FILING_ID,
                to_id=VORA_ROOT_ID,
                designation="nominee_director",
                confidence=_pf(0.55),
                nominee_flag="nominee_suspected",
                rationale="MCA explicitly designates appointment as nominee_director",
            ),
            UBOEdge(
                kind="owns",
                from_id=DEVANSH_ID,
                to_id=VORA_ROOT_ID,
                ownership_pct=5.0,
                confidence=_pf(0.92),
            ),
            UBOEdge(
                kind="owns",
                from_id=COASTAL_ID,
                to_id=VORA_ROOT_ID,
                ownership_pct=70.0,
                confidence=_pf(0.55),
                nominee_flag="nominee_suspected",
                rationale="Foreign corporate holder (SG) with 70.0% ownership; structure suggests nominee/shell",
            ),
            UBOEdge(
                kind="owns",
                from_id=ANCHOR_ID,
                to_id=VORA_ROOT_ID,
                ownership_pct=25.0,
                confidence=_pf(0.55),
                nominee_flag="nominee_suspected",
                rationale="Foreign corporate holder (VG) with 25.0% ownership; structure suggests nominee/shell",
            ),
        ],
    )
