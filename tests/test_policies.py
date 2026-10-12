# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for compliance policies (ADR-019)."""

import pathlib
import re
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from chronowarden.config import AppConfig, ControlThresholds

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
