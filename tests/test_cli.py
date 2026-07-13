"""CLI unit tests (no live cloud)."""

from dimplex_controller.cli import _redact, build_parser, main


def test_redact_hides_secrets_by_default():
    assert _redact("abcdefghijklmnop", show=False).startswith("abcd")
    assert "ijklmnop" not in _redact("abcdefghijklmnop", show=False)
    assert _redact("abcdefghijklmnop", show=True) == "abcdefghijklmnop"
    assert _redact(None, show=False) == "(none)"


def test_parser_has_core_commands():
    parser = build_parser()
    # argparse stores subparsers on _subparsers
    actions = {a.dest for a in parser._actions}
    assert "command" in actions


def test_main_exits_without_tokens(monkeypatch):
    monkeypatch.delenv("DIMPLEX_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("DIMPLEX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("DIMPLEX_TOKENS_FILE", raising=False)
    code = main(["hubs"])
    assert code == 2
