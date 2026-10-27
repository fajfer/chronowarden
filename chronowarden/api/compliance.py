# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for compliance evidence: summary, gaps, reporting periods and snapshots (#94)."""

import asyncio
import json
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Any, Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from chronowarden.alerting.engine import evaluate_inventory
from chronowarden.api.audit import request_source
from chronowarden.api.cooldown import Cooldown, enforce
from chronowarden.auth import admin_only, authenticated, request_actor
from chronowarden.compliance.evidence import (
    GAP_TYPES,
    build_document,
    gaps_of,
    in_scope,
    rows_to_csv,
    snapshot_row,
    summary,
)
from chronowarden.compliance.periods import ended_periods, period_by_id
from chronowarden.compliance.policies import evaluate_policy
from chronowarden.compliance.report import render_report, reports_available
from chronowarden.config import AppConfig, CompliancePolicy, ComplianceScope
from chronowarden.metadata import parse_date
from chronowarden.models.compliance import (
    GapEntry,
    GapReport,
    PeriodStatus,
    PolicyDefinition,
    PolicyEvaluation,
    PolicyTrendPoint,
    Snapshot,
    SnapshotCreate,
    SnapshotInfo,
)
from chronowarden.timestamps import utc_timestamp

router = APIRouter(prefix="/compliance", tags=["compliance"], dependencies=[Depends(authenticated)])

_snapshot_cooldown = Cooldown()


def _get_app_dependencies() -> tuple[Any, AppConfig]:
    """Get the database and config from the app module."""
    from chronowarden.app import app_config, db

    return db, app_config


def _secrets(database: Any, config: AppConfig, include_removed: bool = False) -> list:
    from chronowarden.api.secrets import enriched_secrets

    return enriched_secrets(database, config, include_removed=include_removed)


def _scope_from_query(
    vaults: list[str], engines: list[str], systems: list[str], privileged_only: bool
) -> ComplianceScope:
    return ComplianceScope(vaults=vaults, engines=engines, systems=systems, privileged_only=privileged_only)


def _cadence_scope(config: AppConfig, cadence: str) -> ComplianceScope:
    """
    Return the configured scope of a cadence.

    Raises:
        HTTPException: 422 if the cadence isn't configured.
    """
    for configured in config.compliance.reporting.cadences:
        if configured.period == cadence:
            return configured.scope
    raise HTTPException(status_code=422, detail=f"No '{cadence}' reporting cadence is configured")


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@router.get("/settings", summary="Compliance settings from config.yaml (read-only)")
async def get_settings() -> dict[str, Any]:
    """
    Show the settings that shape compliance evidence; they are edited in config.yaml only (until 0.9).

    Returns:
        Reporting cadences, the confirmation grace periods and the confirmation_required cascade; never addresses
        or credentials.
    """
    _, config = _get_app_dependencies()
    return {
        "reporting": config.compliance.reporting.model_dump(),
        "confirmation_grace": config.confirmation_grace,
        "confirmation_grace_by_profile": {
            name: profile.confirmation_grace
            for name, profile in sorted(config.expiry_profiles.items())
            if profile.confirmation_grace
        },
        "confirmation_required": [
            {
                "vault": vault.name,
                "required": vault.confirmation_required,
                "engines": [
                    {
                        "engine": engine.name,
                        "required": engine.confirmation_required,
                        "secrets": [
                            {"path": secret.path, "required": secret.confirmation_required}
                            for secret in engine.secrets
                            if secret.confirmation_required is not None
                        ],
                    }
                    for engine in vault.engines
                ],
            }
            for vault in config.vaults
        ],
    }


@router.get("/summary", summary="Total and privileged secrets per vault, engine and system")
async def get_summary() -> dict[str, list[dict[str, Any]]]:
    """
    Count secrets that exist in their backend.

    Returns:
        Counts by vault, by engine and by system (system null = unassigned).
    """
    database, config = _get_app_dependencies()
    return summary(_secrets(database, config))


@router.get("/gaps", response_model=GapReport, summary="Evidence gaps in a scope")
async def get_gaps(
    vaults: list[str] = Query(default_factory=list),
    engines: list[str] = Query(default_factory=list),
    systems: list[str] = Query(default_factory=list),
    privileged_only: bool = Query(False),
    cadence: Optional[str] = Query(None, description="Use a configured cadence's scope instead"),
) -> GapReport:
    """
    List secrets in scope with no effective owner, no system, an expired or missing TTL, privileged without an
    owner, or a rotation awaiting confirmation.

    Returns:
        The gaps per secret and per type.
    """
    database, config = _get_app_dependencies()
    scope = _cadence_scope(config, cadence) if cadence else _scope_from_query(vaults, engines, systems, privileged_only)
    secrets = [s for s in _secrets(database, config) if in_scope(s, scope)]
    entries = [GapEntry(id=s.id, full_path=s.full_path, gaps=gaps_of(s)) for s in secrets]
    with_gaps = [entry for entry in entries if entry.gaps]
    counts = {gap: sum(gap in entry.gaps for entry in with_gaps) for gap in GAP_TYPES}
    return GapReport(scope=scope, total=len(secrets), counts=counts, secrets=with_gaps)


@router.get("/periods", response_model=list[PeriodStatus], summary="Reporting periods and whether they were closed")
async def get_periods() -> list[PeriodStatus]:
    """
    List, per configured cadence, the periods that ended since the audit log started, oldest first.

    Returns:
        Each period with the latest snapshot closing it, or none (it still needs closing).
    """
    database, config = _get_app_dependencies()
    started = parse_date(database.first_audit_timestamp() or "") or _now()
    closed: dict[tuple[str, str], int] = {}
    for snapshot in reversed(database.list_snapshots()):
        if snapshot["cadence"]:
            closed[(snapshot["cadence"], snapshot["period"])] = snapshot["id"]
    result = []
    for cadence in config.compliance.reporting.cadences:
        for period in ended_periods(cadence.period, started, _now()):
            result.append(
                PeriodStatus(
                    cadence=period.cadence,
                    period=period.id,
                    start=utc_timestamp(period.start),
                    end=utc_timestamp(period.end),
                    snapshot_id=closed.get((period.cadence, period.id)),
                )
            )
    return result


@router.get("/snapshots", response_model=list[SnapshotInfo], summary="List snapshots")
async def list_snapshots() -> list[SnapshotInfo]:
    """List snapshots, newest first."""
    database, _ = _get_app_dependencies()
    return [SnapshotInfo(**row) for row in database.list_snapshots()]


@router.post(
    "/snapshots",
    dependencies=[Depends(admin_only)],
    response_model=SnapshotInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Take a snapshot",
)
async def create_snapshot(data: SnapshotCreate, request: Request) -> SnapshotInfo:
    """
    Freeze the inventory of a scope: ad hoc (label + scope) or for an ended reporting period (scope from config).

    Periodic snapshots also include secrets removed during the period. Closing a period again needs `supersedes`
    pointing at its latest snapshot (a correction). Gaps aren't recorded; check `GET /compliance/gaps` first.

    Returns:
        The new snapshot.

    Raises:
        HTTPException: 422 for an unknown cadence, a malformed or unfinished period or an unknown `supersedes`;
            409 when the period is already closed and `supersedes` doesn't name its latest snapshot; 429 within
            `snapshot_min_interval` of the last snapshot taken on request.
    """
    database, config = _get_app_dependencies()
    now = _now()
    if data.supersedes is not None and database.get_snapshot(data.supersedes) is None:
        raise HTTPException(status_code=422, detail=f"Snapshot {data.supersedes} doesn't exist")
    if data.cadence is not None and data.period is not None:
        scope = _cadence_scope(config, data.cadence)
        try:
            period = period_by_id(data.cadence, data.period)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        if period.end > now:
            raise HTTPException(
                status_code=422, detail=f"Period {period.id} hasn't ended yet (ends {utc_timestamp(period.end)})"
            )
        latest = next(
            (s for s in database.list_snapshots() if s["cadence"] == data.cadence and s["period"] == data.period), None
        )
        if latest is not None and data.supersedes != latest["id"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Period {period.id} was closed by snapshot {latest['id']}; "
                    f"send supersedes={latest['id']} to correct it"
                ),
            )
        secrets = [
            s
            for s in _secrets(database, config, include_removed=True)
            if in_scope(s, scope) and (s.removed_at is None or s.removed_at >= period.start)
        ]
    else:
        scope = data.scope or ComplianceScope()
        secrets = [s for s in _secrets(database, config) if in_scope(s, scope)]
    # After validation, so a rejected request doesn't start the interval
    enforce(_snapshot_cooldown, "snapshot", config.snapshot_min_interval, "A snapshot")
    systems = {system["id"]: system for system in database.list_systems()}
    created_at = utc_timestamp(now)
    content, sha256 = build_document(
        [snapshot_row(s, systems) for s in secrets],
        created_at,
        scope,
        database.audit_head(),
        label=data.label,
        cadence=data.cadence,
        period=data.period,
        supersedes=data.supersedes,
        policies=[evaluate_policy(policy, secrets, now) for policy in config.compliance.policies],
    )
    snapshot_id = database.add_snapshot(
        created_at, content, sha256, len(secrets), data.label, data.cadence, data.period, data.supersedes
    )
    if snapshot_id is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database isn't available")
    database.append_audit_event(
        "compliance.snapshot",
        request_source(request),
        actor=request_actor(request),
        subject=f"snapshot:{snapshot_id}",
        after={
            "label": data.label,
            "cadence": data.cadence,
            "period": data.period,
            "sha256": sha256,
            "rows": len(secrets),
            "supersedes": data.supersedes,
        },
    )
    await asyncio.to_thread(evaluate_inventory, database, config, now)  # ComplianceSnapshotCreated (#99)
    return SnapshotInfo(**{k: v for k, v in database.get_snapshot(snapshot_id).items() if k != "content"})


def _require_policy(config: AppConfig, policy_id: str) -> CompliancePolicy:
    """
    Return a configured policy.

    Raises:
        HTTPException: 404 if no policy has this id.
    """
    policy = next((p for p in config.compliance.policies if p.id == policy_id), None)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found")
    return policy


@router.get("/policies", response_model=list[PolicyDefinition], summary="Compliance policies from config.yaml")
async def list_policies() -> list[PolicyDefinition]:
    """List the configured policies (read-only; they are edited in config.yaml, ADR-019)."""
    _, config = _get_app_dependencies()
    return [
        PolicyDefinition(
            id=policy.id,
            name=policy.name,
            framework=policy.framework,
            version=policy.version,
            description=policy.description,
            controls=len(policy.controls),
            yaml=yaml.safe_dump(policy.model_dump(exclude_none=True, exclude_defaults=True), sort_keys=False),
        )
        for policy in config.compliance.policies
    ]


@router.get(
    "/policies/{policy_id}/evaluation", response_model=PolicyEvaluation, summary="Evaluate a policy now, with its trend"
)
async def evaluate(policy_id: str) -> PolicyEvaluation:
    """
    Evaluate a policy against the current inventory, with its results in earlier snapshots.

    Raises:
        HTTPException: 404 for an unknown policy.
    """
    database, config = _get_app_dependencies()
    policy = _require_policy(config, policy_id)
    now = _now()
    result = evaluate_policy(policy, _secrets(database, config), now)
    trend = []
    for row in database.snapshot_policy_results(policy_id):
        frozen = json.loads(row["result"])
        trend.append(
            PolicyTrendPoint(
                snapshot_id=row["id"],
                created_at=row["created_at"],
                label=row["label"],
                period=row["period"],
                status=frozen["status"],
                counts=frozen["counts"],
            )
        )
    return PolicyEvaluation(**result, evaluated_at=utc_timestamp(now), trend=trend)


def _require_snapshot(database: Any, snapshot_id: int) -> dict:
    snapshot = database.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot {snapshot_id} not found")
    return snapshot


@router.get("/snapshots/{snapshot_id}.json", summary="Export a snapshot as its canonical JSON")
async def export_snapshot_json(snapshot_id: int) -> Response:
    """Return exactly the hashed bytes, with the hash in `X-Content-SHA256`."""
    database, _ = _get_app_dependencies()
    snapshot = _require_snapshot(database, snapshot_id)
    return Response(
        content=snapshot["content"].encode("utf-8"),
        media_type="application/json",
        headers={
            "X-Content-SHA256": snapshot["sha256"],
            "Content-Disposition": f'attachment; filename="chronowarden-snapshot-{snapshot_id}.json"',
        },
    )


@router.get("/snapshots/{snapshot_id}.csv", summary="Export a snapshot's rows as CSV")
async def export_snapshot_csv(snapshot_id: int) -> Response:
    """Return the rows as CSV; the JSON export is the verifiable form."""
    database, _ = _get_app_dependencies()
    snapshot = _require_snapshot(database, snapshot_id)
    return Response(
        content=rows_to_csv(json.loads(snapshot["content"])["rows"]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="chronowarden-snapshot-{snapshot_id}.csv"'},
    )


@router.get(
    "/snapshots/{snapshot_id}/report.pdf",
    summary="Download a snapshot's PDF report",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def export_snapshot_report(snapshot_id: int) -> Response:
    """
    Render the snapshot's compliance report as PDF/A from the snapshot alone (ADR-020).

    Raises:
        HTTPException: 404 for an unknown snapshot; 501 in the headless image, which has no Typst (ADR-024).
    """
    database, _ = _get_app_dependencies()
    snapshot = _require_snapshot(database, snapshot_id)
    if not reports_available():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF reports aren't available in the headless image; use the default image, or the JSON export",
        )
    pdf = await asyncio.to_thread(render_report, snapshot, f"Chronowarden {version('chronowarden')}")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="chronowarden-report-{snapshot_id}.pdf"'},
    )


@router.get("/snapshots/{snapshot_id}", response_model=Snapshot, summary="Get a snapshot")
async def get_snapshot(snapshot_id: int) -> Snapshot:
    """Return a snapshot with its parsed document."""
    database, _ = _get_app_dependencies()
    snapshot = _require_snapshot(database, snapshot_id)
    content = snapshot.pop("content")
    return Snapshot(**snapshot, document=json.loads(content))
