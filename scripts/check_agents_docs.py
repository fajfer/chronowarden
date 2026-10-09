# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Check agent documentation: AGENTS.md line budgets and relative Markdown links."""

import re
import sys
from pathlib import Path

ROOT_BUDGET_LINES = 150
SCOPED_BUDGET_LINES = 80
SKIPPED_DIRS = {".git", ".venv", "venv", "node_modules", ".svelte-kit", "build", "dist", "__pycache__"}

_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


def iter_agent_docs(repo_root: Path) -> list[Path]:
    """
    Collect every AGENTS.md and every Markdown file under .ai/.

    Args:
        repo_root: Repository root directory.

    Returns:
        Sorted list of documentation files to check.
    """
    docs = [
        path
        for path in repo_root.rglob("AGENTS.md")
        if not SKIPPED_DIRS.intersection(path.relative_to(repo_root).parts)
    ]
    ai_dir = repo_root / ".ai"
    if ai_dir.is_dir():
        docs.extend(ai_dir.rglob("*.md"))
    return sorted(set(docs))


def check_line_budget(path: Path, repo_root: Path) -> list[str]:
    """
    Check that an AGENTS.md file stays within its line budget.

    Args:
        path: File to check.
        repo_root: Repository root directory.

    Returns:
        Error messages; empty when the file is within budget or is not an AGENTS.md.
    """
    if path.name != "AGENTS.md":
        return []
    budget = ROOT_BUDGET_LINES if path.parent == repo_root else SCOPED_BUDGET_LINES
    line_count = len(path.read_text(encoding="utf-8").splitlines())
    if line_count > budget:
        return [f"{path.relative_to(repo_root)}: {line_count} lines exceeds budget of {budget}"]
    return []


def extract_links(text: str) -> list[str]:
    """
    Extract Markdown link targets outside fenced code blocks.

    Args:
        text: Markdown content.

    Returns:
        Link targets in order of appearance.
    """
    links: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            links.extend(_LINK_PATTERN.findall(line))
    return links


def check_links(path: Path, repo_root: Path) -> list[str]:
    """
    Check that every relative link in a Markdown file resolves to an existing path.

    Args:
        path: File to check.
        repo_root: Repository root directory.

    Returns:
        Error messages for broken links.
    """
    errors: list[str] = []
    for target in extract_links(path.read_text(encoding="utf-8")):
        if target.startswith(_EXTERNAL_PREFIXES):
            continue
        file_part = target.split("#", 1)[0]
        if not (path.parent / file_part).exists():
            errors.append(f"{path.relative_to(repo_root)}: broken link '{target}'")
    return errors


def run_checks(repo_root: Path) -> list[str]:
    """
    Run all agent documentation checks.

    Args:
        repo_root: Repository root directory.

    Returns:
        All error messages found.
    """
    errors: list[str] = []
    for path in iter_agent_docs(repo_root):
        errors.extend(check_line_budget(path, repo_root))
        errors.extend(check_links(path, repo_root))
    return errors


def main() -> int:
    """
    Run the checks against the repository containing this script.

    Returns:
        Process exit code: 0 when all checks pass, 1 otherwise.
    """
    repo_root = Path(__file__).resolve().parent.parent
    errors = run_checks(repo_root)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print("Agent docs OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
