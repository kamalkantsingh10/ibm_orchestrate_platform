"""Deterministic Cockpit Chat reply generator — Story 6.8.

Demo simplification: Story 6.7 registered the `cockpit_chat` agent against
cloud Orchestrate (Path B reviewer surface). This module is the
**cockpit-side** chat backend that powers the in-cockpit chat UI without
the cloud round-trip — the demo's typewriter + citation rendering wow
doesn't depend on actual LLM streaming, and a deterministic templated
reply is reliably citation-rich and observable.

The `_generate` function picks one of a few intent-templates from the user
text + the case's ledger state and returns a single reply string. The
streaming task in the route splits this string into ~6-char chunks and
publishes one `cockpit_chat.token` SSE event per chunk so the UI sees the
typewriter effect.
"""

from __future__ import annotations

from collections.abc import Iterable

from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import Case
from contracts.ledger import LedgerEntry


def generate_reply(
    *,
    case: Case,
    ledger_entries: Iterable[LedgerEntry],
    user_message: str,
) -> str:
    """Return a templated reply string. Cites real ledger entry IDs."""
    text = user_message.lower().strip()
    entries = list(ledger_entries)

    # Find the most recent successful agent.completed entries.
    by_actor: dict[str, LedgerEntry] = {}
    for entry in entries:
        if isinstance(entry.payload, AgentActionLedgerEntry) and entry.payload.status == "ok":
            by_actor[entry.actor_id] = entry

    if any(kw in text for kw in ("screening", "amber", "sanction")):
        return _screening_reply(case, by_actor)
    if any(kw in text for kw in ("re-run", "rerun", "run again")):
        return _rerun_reply(case)
    if any(kw in text for kw in ("ubo", "ownership", "shareholder")):
        return _ubo_reply(case, by_actor)
    if any(kw in text for kw in ("risk", "score")):
        return _risk_reply(case, by_actor)
    return _default_reply(case, entries)


def _screening_reply(case: Case, by_actor: dict[str, LedgerEntry]) -> str:
    name = case.customer_metadata.customer_name
    scr = by_actor.get("screening")
    if scr is None:
        return (
            f"I don't have a recent screening run for {name}. Try clicking "
            f"'Process now' on the case canvas to trigger intake."
        )
    payload = scr.payload
    open_hits: list[str] = []
    if isinstance(payload, AgentActionLedgerEntry) and payload.output:
        for hit in payload.output.get("hits", []):
            if hit.get("disposition") == "open":
                open_hits.append(
                    f"{hit.get('matched_name', '?')} "
                    f"({', '.join(hit.get('categories', []))}) "
                    f"at {round(hit.get('name_match_score', {}).get('value', 0) * 100)}%"
                )
    if not open_hits:
        return f"Screening returned no officer-actionable hits for {name} ({scr.id}). The case can proceed."
    hits_summary = "; ".join(open_hits)
    return (
        f"Screening returned {len(open_hits)} open hit(s) for {name}: {hits_summary}. "
        f"Click the citation {scr.id} to see the full reasoning trace."
    )


def _ubo_reply(case: Case, by_actor: dict[str, LedgerEntry]) -> str:
    name = case.customer_metadata.customer_name
    ubo = by_actor.get("ubo_graph")
    if ubo is None:
        return f"No UBO graph has been built for {name}."
    payload = ubo.payload
    flagged = 0
    nodes = 0
    if isinstance(payload, AgentActionLedgerEntry) and payload.output:
        nodes = len(payload.output.get("nodes", []))
        flagged = sum(1 for e in payload.output.get("edges", []) if e.get("nominee_flag") == "nominee_suspected")
    return (
        f"The UBO graph for {name} has {nodes} node(s); {flagged} edge(s) are flagged as nominee-suspected ({ubo.id})."
    )


def _risk_reply(case: Case, by_actor: dict[str, LedgerEntry]) -> str:
    name = case.customer_metadata.customer_name
    risk = by_actor.get("risk_scoring")
    if risk is None:
        return f"No risk score has been computed for {name}."
    payload = risk.payload
    if isinstance(payload, AgentActionLedgerEntry) and payload.output:
        total = payload.output.get("total")
        band = payload.output.get("band")
        return f"{name} scored {total} / 100 ({band}) on the latest risk computation ({risk.id})."
    return f"Risk score available — see {risk.id}."


def _rerun_reply(case: Case) -> str:
    return (
        f"Should I re-run screening on {case.customer_metadata.customer_name}? "
        f"This will write a new agent.completed ledger entry. Reply 'yes' to "
        f"proceed."
    )


def _default_reply(case: Case, entries: list[LedgerEntry]) -> str:
    name = case.customer_metadata.customer_name
    cited = entries[-1].id if entries else "led_<none>"
    return (
        f"I can answer questions about {name}'s screening, UBO graph, risk "
        f"score, or any specific agent action. Try 'explain why screening is "
        f"amber' or 'what's the risk score?'. Most recent entry: {cited}."
    )


def chunk_reply(text: str, *, chunk_size: int = 6) -> list[str]:
    """Split a reply into ~`chunk_size`-char chunks for the typewriter SSE.

    Splits on word boundaries when possible so the visual is natural;
    falls back to fixed-size for long unbroken substrings.
    """
    chunks: list[str] = []
    buf: list[str] = []
    cur_len = 0
    for word in text.split(" "):
        w = (" " if buf else "") + word
        if cur_len + len(w) > chunk_size and buf:
            chunks.append("".join(buf))
            buf = [word]
            cur_len = len(word)
        else:
            buf.append(w)
            cur_len += len(w)
    if buf:
        chunks.append("".join(buf))
    return chunks
