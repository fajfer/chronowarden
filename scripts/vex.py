#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""
Write the CycloneDX VEX for one SBOM from the statements in `vex/chronowarden.vex.cdx.json` (ADR-030).

The statements name components by package URL; scanners match a VEX to an SBOM by BOM-Link
(`urn:cdx:<serial>/<version>#<bom-ref>`), and every SBOM gets a new serial number. So each statement's `affects` is
rewritten to the BOM-Links of the SBOM's components with that package URL (qualifiers ignored), and a statement
whose components the SBOM doesn't contain is left out.

Usage: `scripts/vex.py SBOM STATEMENTS OUT`. Standard library only: it runs in the release workflows as is.
"""

import argparse
import copy
import json
import re
import sys
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

SERIAL = re.compile(r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# CycloneDX 1.6 impactAnalysisJustification
JUSTIFICATIONS = frozenset(
    {
        "code_not_present",
        "code_not_reachable",
        "requires_configuration",
        "requires_dependency",
        "requires_environment",
        "protected_by_compiler",
        "protected_at_runtime",
        "protected_at_perimeter",
        "protected_by_mitigating_control",
    }
)


class VexError(Exception):
    """The statements or the SBOM can't be turned into a VEX."""


def purl_key(purl: str) -> str:
    """A package URL without qualifiers (`?...`) or subpath (`#...`): what a statement and a component share."""
    return purl.split("#", 1)[0].split("?", 1)[0]


def bom_link(serial: str, version: int, bom_ref: str) -> str:
    """The BOM-Link of a component, encoded as cyclonedx-go (used by trivy) writes and reads it."""
    return f"urn:cdx:{serial.removeprefix('urn:uuid:')}/{version}#{quote_plus(bom_ref, safe='')}"


def _components(items: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Every component, nested ones included."""
    for item in items:
        yield item
        yield from _components(item.get("components", []))


def check_statements(statements: dict[str, Any]) -> list[dict[str, Any]]:
    """
    The statements' vulnerabilities, each a complete `not_affected` statement.

    Raises:
        VexError: Naming the first statement that lacks an ID, the state, a known justification, a detail or
            affected package URLs.
    """
    if statements.get("bomFormat") != "CycloneDX" or not isinstance(statements.get("vulnerabilities"), list):
        raise VexError("statements: not a CycloneDX document with a vulnerabilities list")
    for vuln in statements["vulnerabilities"]:
        name = vuln.get("id") or "<no id>"
        analysis = vuln.get("analysis", {})
        if not vuln.get("id"):
            raise VexError("statements: a vulnerability has no id")
        if analysis.get("state") != "not_affected":
            raise VexError(f"{name}: analysis.state must be not_affected (ADR-030)")
        if analysis.get("justification") not in JUSTIFICATIONS:
            raise VexError(f"{name}: unknown justification {analysis.get('justification')!r}")
        if not str(analysis.get("detail", "")).strip():
            raise VexError(f"{name}: analysis.detail must say what was checked")
        refs = [affect.get("ref", "") for affect in vuln.get("affects", [])]
        if not refs or not all(ref.startswith("pkg:") for ref in refs):
            raise VexError(f"{name}: affects must list package URLs")
    return statements["vulnerabilities"]


def for_sbom(statements: dict[str, Any], sbom: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """
    The VEX for `sbom`: the statements whose components it contains, pointing at them by BOM-Link.

    Raises:
        VexError: If the statements are incomplete or the SBOM has no valid serial number and version.
    """
    vulnerabilities = check_statements(statements)
    serial, version = sbom.get("serialNumber", ""), sbom.get("version")
    if not SERIAL.fullmatch(serial) or not isinstance(version, int) or version < 1:
        raise VexError("SBOM: needs a urn:uuid serialNumber and a version >= 1")
    refs: dict[str, list[str]] = {}
    for component in _components(sbom.get("components", [])):
        if component.get("purl") and component.get("bom-ref"):
            refs.setdefault(purl_key(component["purl"]), []).append(component["bom-ref"])
    kept = []
    for vuln in vulnerabilities:
        links = [
            bom_link(serial, version, bom_ref)
            for affect in vuln["affects"]
            for bom_ref in refs.get(purl_key(affect["ref"]), [])
        ]
        if links:
            entry = copy.deepcopy(vuln)
            entry["affects"] = [{"ref": link} for link in links]
            kept.append(entry)
    metadata: dict[str, Any] = {"timestamp": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if "component" in sbom.get("metadata", {}):
        metadata["component"] = copy.deepcopy(sbom["metadata"]["component"])
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": metadata,
        "vulnerabilities": kept,
    }


def main(argv: list[str] | None = None) -> int:
    """Write the VEX for one SBOM; returns the exit code."""
    parser = argparse.ArgumentParser(description="Write the CycloneDX VEX for one SBOM (ADR-030).")
    parser.add_argument("sbom", type=Path, help="a CycloneDX SBOM (JSON)")
    parser.add_argument("statements", type=Path, help="vex/chronowarden.vex.cdx.json")
    parser.add_argument("out", type=Path, help="where to write the VEX")
    args = parser.parse_args(argv)
    try:
        vex = for_sbom(json.loads(args.statements.read_text()), json.loads(args.sbom.read_text()))
    except (OSError, json.JSONDecodeError, VexError) as exc:
        print(f"vex: {exc}", file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(vex, indent=2) + "\n")
    print(f"vex: {args.out}: {len(vex['vulnerabilities'])} statement(s) for {args.sbom.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
