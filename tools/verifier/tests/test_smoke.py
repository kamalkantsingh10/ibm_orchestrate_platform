"""Smoke test: verifier CLI stub is callable.

Real Ed25519 hash-chain verification lands in Story 9.6.
"""

from verifier.cli import main


def test_cli_main_runs(capsys) -> None:  # type: ignore[no-untyped-def]
    main()
    captured = capsys.readouterr()
    assert "verifier stub" in captured.out
