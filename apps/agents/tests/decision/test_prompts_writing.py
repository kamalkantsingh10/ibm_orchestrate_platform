"""Golden tests for the Writing-agent Jinja prompt — Story 7.3 / AC #15.

The hash is the lock: any change to ``rationale_draft_v1.j2`` requires
updating the hash + a code review. NFR-RI7 discipline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "src" / "agents" / "prompts" / "writing"


def _render(case_name: str) -> str:
    env = Environment(
        loader=FileSystemLoader(_PROMPT_DIR),
        autoescape=select_autoescape(default=False),
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    template = env.get_template("rationale_draft_v1.j2")
    data = json.loads((_PROMPT_DIR / "golden" / f"{case_name}_rationale_v1.json").read_text())
    return template.render(**data)


_GOLDEN_HASHES = {
    "vora": "4b1dc026f98b13257a34ac802869d08fa7426263da530bea328bc1abeacf38be",
    "shree": "9e34f10cd0c283d7a79c33c8e41169afc112f284acb3897dc3bad9cbacee40ef",
    "ananya": "d2cba69a6186c9d5bd4e42ee449423e5551b9956a5d36d861ecbe6f052179002",
}


@pytest.mark.parametrize("case_name", ["vora", "shree", "ananya"])
def test_rationale_draft_v1_golden_hash_is_stable(case_name: str) -> None:
    rendered = _render(case_name)
    actual = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    assert actual == _GOLDEN_HASHES[case_name], (
        f"prompt hash drift for {case_name}: expected {_GOLDEN_HASHES[case_name]}, got {actual}\n\n"
        f"Update the hash + the prompt template require code review."
    )


def test_rendered_prompt_contains_no_test_sentinel_strings() -> None:
    """Defensive — assert no leaked PII or test markers in the rendered prompt."""
    for case_name in _GOLDEN_HASHES:
        rendered = _render(case_name).lower()
        for sentinel in ("test_secret_", "todo_remove", "lorem ipsum"):
            assert sentinel not in rendered, f"{sentinel!r} leaked into {case_name} rendered prompt"


def test_vora_prompt_includes_each_agents_ledger_id() -> None:
    """Each ledger_ids map entry must surface in the rendered prompt so the LLM
    can cite by exact id rather than inventing one."""
    rendered = _render("vora")
    for led_id in (
        "led_01ABCDEFGHJKMNPQRSTVWXYZ12",
        "led_01HXY3GHJKMNPQRSTVWXYZ7HX2",
        "led_01HXY4GHJKMNPQRSTVWXYZ7HX3",
        "led_01HXY5GHJKMNPQRSTVWXYZ7HX4",
        "led_01HXY6GHJKMNPQRSTVWXYZ7HX5",
    ):
        assert led_id in rendered


def test_shree_prompt_omits_entity_verification_and_ubo_when_absent() -> None:
    """Goldens with no entity_status / ubo_summary should not render those rows."""
    rendered = _render("shree")
    assert "Entity Verification:" not in rendered
    assert "UBO Graph:" not in rendered
    assert "Screening:" in rendered  # still present


def test_rendered_prompt_includes_strict_json_instruction() -> None:
    """The LLM must be told to return strict JSON; otherwise the watsonx
    parser will fail downstream."""
    rendered = _render("vora")
    assert "Respond with strict JSON" in rendered
    assert '"paragraphs"' in rendered
    assert '"cited_claims"' in rendered
