# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for scripts/vex.py and the VEX statements in vex/ (ADR-030)."""

import copy
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import unquote_plus

import pytest

REPO = Path(__file__).parent.parent
STATEMENTS = REPO / "vex" / "chronowarden.vex.cdx.json"
SERIAL = "urn:uuid:39725ad6-e8b1-4ddb-87ad-cf6d65bc6315"
# The BOM-Link pattern of cyclonedx-go, which trivy uses to read a CycloneDX VEX
BOM_LINK = re.compile(
    r"^urn:cdx:(?P<serial>[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12})/(?P<version>[1-9]\d*)"
    r"(?:#(?P<ref>[\da-zA-Z\-._~%!$&'()*+,;=:@/?]+))?$"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vex", REPO / "scripts" / "vex.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vex = _load()


def _statement(vuln_id: str = "CVE-1", purl: str = "pkg:npm/deepmerge@4.3.1", **analysis: str) -> dict[str, Any]:
    return {
        "id": vuln_id,
        "analysis": {"state": "not_affected", "justification": "code_not_reachable", "detail": "checked", **analysis},
        "affects": [{"ref": purl}],
    }


def _statements(*vulns: dict[str, Any]) -> dict[str, Any]:
    return {"bomFormat": "CycloneDX", "specVersion": "1.6", "vulnerabilities": list(vulns)}


def _sbom(*components: dict[str, Any]) -> dict[str, Any]:
    return {
        "bomFormat": "CycloneDX",
        "serialNumber": SERIAL,
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "chronowarden"}},
        "components": list(components),
    }


def _component(purl: str, ref: str, **extra: Any) -> dict[str, Any]:
    return {"type": "library", "purl": purl, "bom-ref": ref, **extra}


class TestForSbom:
    def test_points_at_the_matching_component_by_bom_link(self) -> None:
        ref = "pkg:npm/deepmerge@4.3.1?package-id=ba97"
        out = vex.for_sbom(_statements(_statement()), _sbom(_component("pkg:npm/deepmerge@4.3.1", ref)))
        (link,) = [affect["ref"] for affect in out["vulnerabilities"][0]["affects"]]
        match = BOM_LINK.match(link)
        assert match is not None
        assert (f"urn:uuid:{match['serial']}", match["version"], unquote_plus(match["ref"])) == (SERIAL, "1", ref)

    def test_keeps_the_analysis_and_identifies_the_product(self) -> None:
        now = datetime(2026, 11, 7, tzinfo=timezone.utc)
        out = vex.for_sbom(_statements(_statement()), _sbom(_component("pkg:npm/deepmerge@4.3.1", "r")), now)
        assert out["vulnerabilities"][0]["analysis"]["detail"] == "checked"
        assert out["metadata"] == {"timestamp": "2026-11-07T00:00:00Z", "component": _sbom()["metadata"]["component"]}
        assert out["serialNumber"] != SERIAL and out["specVersion"] == "1.6"

    def test_drops_a_statement_for_a_component_the_sbom_lacks(self) -> None:
        out = vex.for_sbom(_statements(_statement()), _sbom(_component("pkg:pypi/requests@2.0", "r")))
        assert out["vulnerabilities"] == []

    def test_qualifiers_and_subpaths_are_ignored_when_matching(self) -> None:
        component = _component("pkg:npm/deepmerge@4.3.1?arch=x#sub", "r")
        out = vex.for_sbom(_statements(_statement(purl="pkg:npm/deepmerge@4.3.1?other=y")), _sbom(component))
        assert len(out["vulnerabilities"][0]["affects"]) == 1

    def test_every_matching_component_is_linked_nested_ones_too(self) -> None:
        nested = _component("pkg:npm/deepmerge@4.3.1", "inner")
        outer = _component("pkg:npm/deepmerge@4.3.1", "outer", components=[nested])
        out = vex.for_sbom(_statements(_statement()), _sbom(outer))
        refs = [unquote_plus(a["ref"].split("#", 1)[1]) for a in out["vulnerabilities"][0]["affects"]]
        assert refs == ["outer", "inner"]

    def test_another_version_is_not_matched(self) -> None:
        out = vex.for_sbom(_statements(_statement()), _sbom(_component("pkg:npm/deepmerge@4.3.2", "r")))
        assert out["vulnerabilities"] == []

    def test_the_statements_are_not_changed(self) -> None:
        statements = _statements(_statement())
        before = copy.deepcopy(statements)
        vex.for_sbom(statements, _sbom(_component("pkg:npm/deepmerge@4.3.1", "r")))
        assert statements == before

    @pytest.mark.parametrize("sbom", [{"serialNumber": "abc", "version": 1}, {"serialNumber": SERIAL, "version": 0}])
    def test_an_sbom_without_serial_or_version_fails(self, sbom: dict[str, Any]) -> None:
        with pytest.raises(vex.VexError, match="SBOM"):
            vex.for_sbom(_statements(_statement()), sbom)


class TestStatements:
    @pytest.mark.parametrize(
        ("vuln", "message"),
        [
            ({**_statement(), "id": ""}, "no id"),
            (_statement(state="affected"), "not_affected"),
            (_statement(justification="because"), "unknown justification"),
            (_statement(detail="  "), "detail"),
            ({**_statement(), "affects": []}, "package URLs"),
            (_statement(purl="urn:cdx:x/1#y"), "package URLs"),
        ],
    )
    def test_an_incomplete_statement_fails(self, vuln: dict[str, Any], message: str) -> None:
        with pytest.raises(vex.VexError, match=message):
            vex.check_statements(_statements(vuln))

    def test_not_a_cyclonedx_document_fails(self) -> None:
        with pytest.raises(vex.VexError, match="CycloneDX"):
            vex.check_statements({"vulnerabilities": []})

    def test_the_repository_statements_are_complete(self) -> None:
        """Every statement we publish has the state, a known justification, a detail and package URLs."""
        statements = json.loads(STATEMENTS.read_text())
        assert statements["specVersion"] == "1.6"
        assert vex.check_statements(statements)


class TestMain:
    def test_writes_the_vex(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        sbom, statements, out = tmp_path / "s.cdx.json", tmp_path / "st.json", tmp_path / "out.json"
        sbom.write_text(json.dumps(_sbom(_component("pkg:npm/deepmerge@4.3.1", "r"))))
        statements.write_text(json.dumps(_statements(_statement())))
        assert vex.main([str(sbom), str(statements), str(out)]) == 0
        assert len(json.loads(out.read_text())["vulnerabilities"]) == 1
        assert "1 statement(s)" in capsys.readouterr().out

    def test_bad_input_fails_without_writing(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        sbom, statements, out = tmp_path / "s.cdx.json", tmp_path / "st.json", tmp_path / "out.json"
        sbom.write_text("not json")
        statements.write_text(json.dumps(_statements(_statement())))
        assert vex.main([str(sbom), str(statements), str(out)]) == 1
        assert not out.exists() and "vex:" in capsys.readouterr().err
