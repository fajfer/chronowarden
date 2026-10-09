# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the agent documentation checker script."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "check_agents_docs.py"


def _load_checker() -> ModuleType:
    """Load scripts/check_agents_docs.py as a module."""
    spec = importlib.util.spec_from_file_location("check_agents_docs", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _write_lines(path: Path, count: int) -> None:
    """Write a file with the given number of lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("line\n" * count, encoding="utf-8")


class TestLineBudget:
    """Test AGENTS.md line budgets."""

    def test_root_within_budget(self, tmp_path: Path) -> None:
        """Root file at exactly the budget passes."""
        _write_lines(tmp_path / "AGENTS.md", checker.ROOT_BUDGET_LINES)
        assert checker.run_checks(tmp_path) == []

    def test_root_over_budget(self, tmp_path: Path) -> None:
        """Root file over the budget fails."""
        _write_lines(tmp_path / "AGENTS.md", checker.ROOT_BUDGET_LINES + 1)
        errors = checker.run_checks(tmp_path)
        assert len(errors) == 1
        assert "exceeds budget of 150" in errors[0]

    def test_scoped_over_budget(self, tmp_path: Path) -> None:
        """Scoped file uses the smaller budget."""
        _write_lines(tmp_path / "module" / "AGENTS.md", checker.SCOPED_BUDGET_LINES + 1)
        errors = checker.run_checks(tmp_path)
        assert errors == [f"module/AGENTS.md: {checker.SCOPED_BUDGET_LINES + 1} lines exceeds budget of 80"]

    def test_other_markdown_has_no_budget(self, tmp_path: Path) -> None:
        """Long .ai documents are not budget-checked."""
        _write_lines(tmp_path / ".ai" / "docs" / "long.md", 500)
        assert checker.run_checks(tmp_path) == []

    def test_skipped_dirs_are_ignored(self, tmp_path: Path) -> None:
        """AGENTS.md inside node_modules is not checked."""
        _write_lines(tmp_path / "frontend" / "node_modules" / "pkg" / "AGENTS.md", 500)
        assert checker.run_checks(tmp_path) == []


class TestLinks:
    """Test relative link resolution."""

    def test_resolving_link_passes(self, tmp_path: Path) -> None:
        """A link to an existing file passes, including a fragment."""
        (tmp_path / "target.md").write_text("x", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("[t](target.md#section)\n", encoding="utf-8")
        assert checker.run_checks(tmp_path) == []

    def test_broken_link_fails(self, tmp_path: Path) -> None:
        """A link to a missing file is reported relative to the repo root."""
        (tmp_path / ".ai").mkdir()
        (tmp_path / ".ai" / "lessons.md").write_text("[gone](missing.md)\n", encoding="utf-8")
        assert checker.run_checks(tmp_path) == [".ai/lessons.md: broken link 'missing.md'"]

    @pytest.mark.parametrize("target", ["https://example.com", "http://localhost:1/sse", "mailto:a@b.c", "#anchor"])
    def test_external_links_are_skipped(self, tmp_path: Path, target: str) -> None:
        """External URLs and same-page anchors are not resolved on disk."""
        (tmp_path / "AGENTS.md").write_text(f"[x]({target})\n", encoding="utf-8")
        assert checker.run_checks(tmp_path) == []

    def test_links_in_code_fences_are_ignored(self, tmp_path: Path) -> None:
        """Example links inside fenced code blocks are not checked."""
        (tmp_path / "AGENTS.md").write_text("```markdown\n[x](nope.md)\n```\n", encoding="utf-8")
        assert checker.run_checks(tmp_path) == []


class TestMain:
    """Test the script entry point."""

    def test_repository_docs_pass(self) -> None:
        """The repository's own agent docs pass the checks."""
        assert checker.main() == 0
