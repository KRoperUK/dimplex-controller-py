"""Tests for the maintenance scripts in scripts/.

These do not exercise any library code, so running this file on its own
(``pytest tests/test_repo_scripts.py``) makes the project's 80% coverage gate
fail with a misleading 0% report. Always run the full suite (``pytest``) in CI
and locally, or pass ``--no-cov`` explicitly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import dimplex_controller  # noqa: F401  (see module docstring)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check-md-alerts.sh"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_check_md_alerts_passes() -> None:
    """Every GitHub alert in tracked Markdown must be renderable as a callout."""
    result = _run()
    assert result.returncode == 0, f"broken GitHub alert:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert "✓" in result.stdout


def test_check_md_alerts_catches_a_joined_marker(tmp_path: Path) -> None:
    """A marker with body text on the same line renders as literal text."""
    broken = tmp_path / "broken.md"
    broken.write_text("> [!IMPORTANT] joined to the text below\n", encoding="utf-8")

    result = _run(str(broken))

    assert result.returncode == 1
    # The ::error annotation (stdout) is what GitHub surfaces on the PR diff.
    assert "not alone on its line" in result.stdout


def test_check_md_alerts_catches_an_unquoted_marker(tmp_path: Path) -> None:
    """A marker outside a blockquote renders as literal text."""
    broken = tmp_path / "unquoted.md"
    broken.write_text("[!WARNING]\nnot in a blockquote\n", encoding="utf-8")

    result = _run(str(broken))

    assert result.returncode == 1
    assert "not in a blockquote" in result.stdout


def test_check_md_alerts_ignores_fenced_code_blocks(tmp_path: Path) -> None:
    """A documentation example is allowed to show the broken form."""
    doc = tmp_path / "guide.md"
    doc.write_text("```markdown\n> [!NOTE] this is how *not* to do it\n```\n", encoding="utf-8")

    assert _run(str(doc)).returncode == 0


def test_check_md_alerts_script_is_executable() -> None:
    """The script needs the executable bit so CI can run it directly."""
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, f"{SCRIPT} is not executable"
