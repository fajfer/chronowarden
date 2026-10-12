# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for compliance policies (ADR-019)."""

import hashlib
import io
import json
import pathlib
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader

from chronowarden.api.compliance import router as compliance_router
from chronowarden.compliance.evidence import build_document
from chronowarden.compliance.policies import evaluate_policy, fails, in_control_scope, rag
from chronowarden.compliance.report import render_report
from chronowarden.config import AppConfig, CompliancePolicy, ComplianceScope, ControlScope, ControlThresholds
from chronowarden.database import Database, SecretMetadataCache
from chronowarden.models.secret import SecretMetadataResponse, SecretStatus
from chronowarden.models.system import OwnerRef, SystemRef

REPO = pathlib.Path(__file__).resolve().parent.parent


def _policy(**control: Any) -> dict[str, Any]:
    return {"id": "p1", "name": "Policy", "controls": [{"id": "C-1", "title": "T", **control}]}


def _config(*policies: dict[str, Any], **extra: Any) -> AppConfig:
    return AppConfig.model_validate({"compliance": {"policies": list(policies)}, **extra})


class TestPolicyConfig:
    def test_valid_policy_with_every_rule_type(self) -> None:
        rules = [
            {"type": "max_rotation_age", "days": 90},
            {"type": "not_expired"},
            {"type": "has_owner"},
            {"type": "has_system"},
            {"type": "rotation_confirmed"},
        ]
        policy = {
            "id": "bank-pam",
            "name": "PAM",
            "framework": "Internal",
            "version": "2026.1",
            "controls": [
                {"id": f"C-{i}", "title": "T", "rule": rule, "scope": {"privileged": True, "paths": ["prod/*"]}}
                for i, rule in enumerate(rules)
            ],
        }
        config = _config(policy)
        assert [c.rule.type for c in config.compliance.policies[0].controls] == [r["type"] for r in rules]
        assert config.compliance.policies[0].controls[0].rule.days == 90  # type: ignore[union-attr]

    def test_no_policies_by_default(self) -> None:
        assert AppConfig().compliance.policies == []

    @pytest.mark.parametrize(
        "rule,message",
        [
            ({"type": "reviewed_quarterly"}, "does not match any of the expected tags"),
            ({"type": "max_rotation_age"}, "days"),
            ({"type": "max_rotation_age", "days": 0}, "greater than or equal to 1"),
            ({"type": "has_owner", "days": 3}, "Extra inputs are not permitted"),
        ],
    )
    def test_invalid_rules(self, rule: dict[str, Any], message: str) -> None:
        with pytest.raises(ValidationError, match=message):
            _config(_policy(rule=rule))

    def test_duplicate_ids(self) -> None:
        with pytest.raises(ValidationError, match="duplicate compliance policy id"):
            _config(_policy(rule={"type": "has_owner"}), _policy(rule={"type": "has_system"}))
        twice = {"id": "p1", "name": "P", "controls": [{"id": "C", "title": "T", "rule": {"type": "has_owner"}}] * 2}
        with pytest.raises(ValidationError, match="duplicate control id"):
            _config(twice)

    @pytest.mark.parametrize("policy_id", ["Bank PAM", "-x", "a/b", ""])
    def test_policy_id_is_url_safe(self, policy_id: str) -> None:
        with pytest.raises(ValidationError):
            _config({**_policy(rule={"type": "has_owner"}), "id": policy_id})

    def test_policy_needs_a_control(self) -> None:
        with pytest.raises(ValidationError):
            _config({"id": "p1", "name": "P", "controls": []})

    def test_scope_names_must_exist(self) -> None:
        with pytest.raises(ValidationError, match="unknown vault"):
            _config(_policy(rule={"type": "has_owner"}, scope={"vaults": ["nope"]}))
        with pytest.raises(ValidationError, match="unknown severity"):
            _config(_policy(rule={"type": "has_owner"}, scope={"severities": ["urgent"]}))
        assert _config(_policy(rule={"type": "has_owner"}, scope={"severities": ["critical", "none"]}))

    @pytest.mark.parametrize(
        "thresholds",
        [{"amber": 5, "red": 2}, {"amber_pct": 50, "red_pct": 10}, {"amber": 1, "red_pct": 10}, {"red_pct": 101}],
    )
    def test_invalid_thresholds(self, thresholds: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            ControlThresholds.model_validate(thresholds)

    def test_example_policy_in_config_example_is_valid(self) -> None:
        """The commented policies example in config.example.yaml, uncommented, passes strict validation."""
        text = (REPO / "config.example.yaml").read_text(encoding="utf-8")
        block = re.search(r"^  # policies:\n((?:  #.*\n)+)", text, re.M)
        assert block is not None
        lines = [re.sub(r"^  # ?", "", line) for line in block.group(0).splitlines()]
        data = yaml.safe_load("\n".join(lines))
        config = _config(*data["policies"])
        assert [c.id for c in config.compliance.policies[0].controls] == ["PAM-01", "PAM-02"]


NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def _secret(path: str = "app/db", **fields: Any) -> SecretMetadataResponse:
    return SecretMetadataResponse(
        id=1, vault_name="prod", engine_id="apps", secret_path=path, full_path=f"prod/apps/{path}", **fields
    )


def _rule(**rule: Any) -> Any:
    return CompliancePolicy.model_validate(_policy(rule=rule)).controls[0].rule


class TestRules:
    def test_max_rotation_age_edges(self) -> None:
        rule = _rule(type="max_rotation_age", days=90)
        exactly = (NOW - timedelta(days=90)).isoformat().replace("+00:00", "Z")
        older = (NOW - timedelta(days=90, seconds=1)).isoformat().replace("+00:00", "Z")
        assert not fails(_secret(updated_time=exactly), rule, NOW)
        assert fails(_secret(updated_time=older), rule, NOW)
        assert fails(_secret(updated_time=None), rule, NOW), "an unknown rotation date can't prove compliance"

    def test_not_expired(self) -> None:
        rule = _rule(type="not_expired")
        assert fails(_secret(status=SecretStatus.EXPIRED), rule, NOW)
        assert not any(fails(_secret(status=s), rule, NOW) for s in (SecretStatus.WARNING, SecretStatus.NO_TTL))

    def test_has_owner_uses_effective_owners(self) -> None:
        rule = _rule(type="has_owner")
        assert fails(_secret(owners=[]), rule, NOW)
        assert not fails(_secret(effective_owners=[OwnerRef(id="a", name="Alice")]), rule, NOW)

    def test_has_system(self) -> None:
        rule = _rule(type="has_system")
        assert fails(_secret(), rule, NOW)
        assert not fails(_secret(system=SystemRef(id="s", name="Billing")), rule, NOW)

    def test_rotation_confirmed_fails_only_when_overdue(self) -> None:
        rule = _rule(type="rotation_confirmed")
        assert not fails(_secret(awaiting_confirmation=True), rule, NOW), "still within the grace period"
        assert fails(_secret(awaiting_confirmation=True, confirmation_overdue=True), rule, NOW)


class TestScope:
    def test_every_selector(self) -> None:
        secret = _secret("db/main", severity="critical", privileged=True, system=SystemRef(id="s", name="Billing"))
        assert in_control_scope(secret, ControlScope())
        for scope in (
            ControlScope(vaults=["prod"], engines=["apps"], systems=["Billing"], severities=["critical"]),
            ControlScope(paths=["prod/apps/db/*"], privileged=True),
        ):
            assert in_control_scope(secret, scope)
        for scope in (
            ControlScope(vaults=["dev"]),
            ControlScope(systems=["CRM"]),
            ControlScope(severities=["default"]),
            ControlScope(paths=["prod/other/*"]),
            ControlScope(privileged=False),
        ):
            assert not in_control_scope(secret, scope)
        assert not in_control_scope(_secret(), ControlScope(systems=["Billing"])), "unassigned is outside"


class TestThresholds:
    @pytest.mark.parametrize(
        "failing,total,thresholds,expected",
        [
            (0, 10, {}, "green"),
            (1, 10, {}, "red"),
            (3, 0, {"red": 1}, "green"),
            (1, 10, {"amber": 2, "red": 5}, "green"),
            (2, 10, {"amber": 2, "red": 5}, "amber"),
            (5, 10, {"amber": 2, "red": 5}, "red"),
            (3, 10, {"red": 5}, "green"),
            (3, 10, {"amber": 1}, "amber"),
            (1, 10, {"amber_pct": 10, "red_pct": 50}, "amber"),
            (1, 11, {"amber_pct": 10, "red_pct": 50}, "green"),
            (5, 10, {"amber_pct": 10, "red_pct": 50}, "red"),
        ],
    )
    def test_rag(self, failing: int, total: int, thresholds: dict[str, Any], expected: str) -> None:
        assert rag(failing, total, ControlThresholds.model_validate(thresholds)) == expected


def test_evaluate_policy_skips_removed_and_takes_the_worst_status() -> None:
    policy = CompliancePolicy.model_validate(
        {
            "id": "p",
            "name": "P",
            "controls": [
                {"id": "OWN", "title": "Owner", "rule": {"type": "has_owner"}, "thresholds": {"amber": 1, "red": 3}},
                {"id": "EXP", "title": "Not expired", "rule": {"type": "not_expired"}},
            ],
        }
    )
    secrets = [
        _secret("b", effective_owners=[OwnerRef(id="a", name="Alice")]),
        _secret("a"),
        _secret("gone", removed_at=NOW, status=SecretStatus.EXPIRED),
    ]
    result = evaluate_policy(policy, secrets, NOW)
    own, exp = result["controls"]
    assert (own["in_scope"], own["failing"], own["status"]) == (2, 1, "amber")
    assert own["failing_secrets"] == [{"full_path": "prod/apps/a", "owners": []}]
    assert (exp["failing"], exp["status"]) == (0, "green"), "the removed, expired secret isn't held any more"
    assert (result["status"], result["counts"]) == ("amber", {"green": 1, "amber": 1, "red": 0})


POLICY = {
    "id": "pam",
    "name": "PAM",
    "framework": "Internal",
    "controls": [
        {
            "id": "PAM-01",
            "title": "Privileged have an owner",
            "scope": {"privileged": True},
            "rule": {"type": "has_owner"},
        },
        {"id": "PAM-02", "title": "Everything has a system", "rule": {"type": "has_system"}},
    ],
}


@pytest.fixture
def client(db: Database) -> Iterator[TestClient]:
    for path, privileged in (("db", True), ("api", False)):
        db.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name="prod", engine_id="apps", secret_path=path, ttl="2030-01-01", privileged=privileged
            )
        )
    config = AppConfig.model_validate(
        {
            "vaults": [{"name": "prod", "address": "http://v:8200", "token": "t"}],
            "compliance": {"policies": [POLICY]},
        }
    )
    app = FastAPI()
    app.include_router(compliance_router, prefix="/api/v1")
    with (
        patch("chronowarden.api.compliance._get_app_dependencies", return_value=(db, config)),
        patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, config, None)),
    ):
        yield TestClient(app)


class TestApi:
    def test_list_policies_with_yaml(self, client: TestClient) -> None:
        [policy] = client.get("/api/v1/compliance/policies").json()
        assert (policy["id"], policy["framework"], policy["controls"]) == ("pam", "Internal", 2)
        assert yaml.safe_load(policy["yaml"])["controls"][0]["rule"] == {"type": "has_owner"}

    def test_evaluation(self, client: TestClient) -> None:
        result = client.get("/api/v1/compliance/policies/pam/evaluation").json()
        assert result["status"] == "red"
        assert [(c["id"], c["in_scope"], c["failing"]) for c in result["controls"]] == [
            ("PAM-01", 1, 1),
            ("PAM-02", 2, 2),
        ]
        assert result["trend"] == []

    def test_unknown_policy_is_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/compliance/policies/nope/evaluation").status_code == 404

    def test_snapshots_freeze_policy_results_for_the_trend(self, client: TestClient, db: Database) -> None:
        created = client.post("/api/v1/compliance/snapshots", json={"label": "before"}).json()
        document = client.get(f"/api/v1/compliance/snapshots/{created['id']}").json()["document"]
        assert document["format"] == 2
        [frozen] = document["policies"]
        assert frozen["id"] == "pam" and frozen["controls"][0]["title"] == "Privileged have an owner"
        db.create_owner("alice", "Alice", "alice@example.com")
        db.set_secret_owners(("prod", "apps", "db"), ["alice"])
        client.post("/api/v1/compliance/snapshots", json={"label": "after"})
        trend = client.get("/api/v1/compliance/policies/pam/evaluation").json()["trend"]
        assert [(t["label"], t["counts"]["red"]) for t in trend] == [("before", 2), ("after", 1)]

    def test_snapshot_hash_covers_the_policy_results(self, client: TestClient, db: Database) -> None:
        created = client.post("/api/v1/compliance/snapshots", json={"label": "x"}).json()
        content = client.get(f"/api/v1/compliance/snapshots/{created['id']}.json").content
        assert hashlib.sha256(content).hexdigest() == created["sha256"]
        assert json.loads(content)["policies"][0]["id"] == "pam"


def _pdf_text(content: bytes) -> str:
    return " ".join(" ".join(page.extract_text().split()) for page in PdfReader(io.BytesIO(content)).pages)


class TestReport:
    def test_report_pdf_from_a_snapshot(self, client: TestClient) -> None:
        created = client.post("/api/v1/compliance/snapshots", json={"label": "Q3 review"}).json()
        response = client.get(f"/api/v1/compliance/snapshots/{created['id']}/report.pdf")
        assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-") and b"pdfaid:part" in response.content
        text = _pdf_text(response.content)
        for expected in (
            "Secret rotation compliance report",
            "Q3 review",
            created["sha256"],
            "PAM Internal RED",
            "PAM-01 Privileged have an owner Has an owner (its own or its system's). Red from 1 failing. 1 1 RED",
            "PAM-01: failing secrets",
            "prod/apps/db —",
            "Methodology and limitations",
        ):
            assert expected in text, expected

    def test_user_text_is_never_typst_markup(self, db: Database) -> None:
        """Names come from users and backends; the template must show them as text, not run them."""
        content, sha256 = build_document(
            [],
            "2026-10-12T10:00:00.000000Z",
            ComplianceScope(),
            {"events": 0, "head_hash": "0" * 64},
            label='#read("/etc/passwd") $x$ *bold*',
        )
        pdf = render_report({"id": 1, "content": content, "sha256": sha256}, "Chronowarden test")
        text = _pdf_text(pdf)
        assert '#read("/etc/passwd") $x$ *bold*' in text and "root:" not in text
        assert "No compliance policies were configured" in text

    def test_unknown_snapshot_is_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/compliance/snapshots/99/report.pdf").status_code == 404

    def test_without_typst_the_report_is_501(self, client: TestClient) -> None:
        """ADR-024: the headless image keeps the route and says where reports are."""
        created = client.post("/api/v1/compliance/snapshots", json={"label": "x"}).json()
        with patch("chronowarden.api.compliance.reports_available", return_value=False):
            response = client.get(f"/api/v1/compliance/snapshots/{created['id']}/report.pdf")
        assert response.status_code == 501 and "headless" in response.json()["detail"]
        assert client.get(f"/api/v1/compliance/snapshots/{created['id']}.json").status_code == 200


def test_example_policies_in_the_docs_are_valid() -> None:
    """Every policy example in docs/guides/example-policies.md passes strict validation."""
    text = (REPO / "docs/guides/example-policies.md").read_text(encoding="utf-8")
    blocks = [yaml.safe_load(block) for block in re.findall(r"```yaml\n(.*?)```", text, re.S)]
    policies = [policy for block in blocks if isinstance(block, list) for policy in block]
    config = _config(*policies)
    assert [p.id for p in config.compliance.policies] == ["pci-dss-4", "dora-ict"]
    cadences = next(b for b in blocks if isinstance(b, dict))
    assert AppConfig.model_validate(cadences).compliance.reporting.cadences[0].period == "quarterly"
