<!--
SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Development Guidelines

This document contains critical information about working with this codebase. Follow these guidelines precisely.

## Core Development Rules

1. Code Quality
   - Type hints required for all code
   - Public APIs must have docstrings
   - Functions must be focused and small
   - Follow existing patterns exactly
   - Line length: 120 chars maximum
   - Each time, you add a new integration make changes to the architecture as well

2. Testing Requirements
   - Coverage: test edge cases and errors
   - New features require tests
   - Bug fixes require regression tests

3. Code Style
    - PEP 8 naming (snake_case for functions/variables)
    - Class names in PascalCase
    - Constants in UPPER_SNAKE_CASE
    - Document with docstrings
    - Use f-strings for formatting

4. Licensing
  - Always input SPDX-compliant headers to files
  - Update SPDX headers for year mismatch
    - eg. if it said 2025-2026 and the current year is 2027, change the date range to 2025-2027

- Use [conventional commits](https://www.conventionalcommits.org/) as a standard for committing
- NEVER ever mention a `co-authored-by` or similar aspects. In particular, never
  mention the tool used to create the commit message or PR.

## Code Formatting

1. Use black for code formatting

2. Type Checking
   - Requirements:
     - Explicit None checks for Optional
     - Type narrowing for strings
     - Version warnings can be ignored if checks pass

## Error Resolution

1. Common Issues
   - Line length:
     - Break strings with parentheses
     - Multi-line function calls
     - Split imports
   - Types:
     - Add None checks
     - Narrow string types
     - Match existing patterns

3. Best Practices
   - Run formatters before type checks
   - Keep changes minimal, only modify code related to the task at hand
   - Follow existing patterns
   - Document public APIs
   - Test thoroughly
   - DRY Code: Don't repeat yourself
   - Start with minimal functionality and verify it works before adding complexity

## System architecture
- Architecture is stored as a code in [architecture](architecture/) directory
  - Always consult [MCP Server endpoint](http://localhost:33335/sse) to get knowledge of architecture model
  - If changes affect architecture, fix architecture accordingly

## Exception Handling

- **Always use `logger.exception()` instead of `logger.error()` when catching exceptions**
  - Don't include the exception in the message: `logger.exception("Failed")` not `logger.exception(f"Failed: {e}")`
- **Catch specific exceptions** where possible:
  - File ops: `except (OSError, PermissionError):`
  - JSON: `except json.JSONDecodeError:`
  - Network: `except (ConnectionError, TimeoutError):`
- **Only catch `Exception` for**:
  - Top-level handlers that must not crash
  - Cleanup blocks (log at debug level)
