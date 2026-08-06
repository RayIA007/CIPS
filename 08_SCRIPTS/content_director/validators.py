from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .models import ContentPackage, ContentStatus


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    path: str
    severity: str = "error"


class ContentDomainValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = tuple(issues)
        summary = "; ".join(f"{issue.code}@{issue.path}: {issue.message}" for issue in self.issues)
        super().__init__(summary or "ContentPackage inválido")


def validate_content_package(package: ContentPackage) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []

    if not package.brief.project_id.strip():
        issues.append(ValidationIssue("brief.project_id.required", "project_id es obligatorio", "brief.project_id"))
    if not package.brief.topic.strip():
        issues.append(ValidationIssue("brief.topic.required", "topic es obligatorio", "brief.topic"))
    if not package.objectives:
        issues.append(ValidationIssue("objectives.required", "Debe existir al menos un objetivo", "objectives"))
    if not package.audiences:
        issues.append(ValidationIssue("audiences.required", "Debe existir al menos una audiencia", "audiences"))
    if not package.pillars:
        issues.append(ValidationIssue("pillars.required", "Debe existir al menos un pilar", "pillars"))
    if not package.channel_plans:
        issues.append(ValidationIssue("channels.required", "Debe existir al menos un plan de canal", "channel_plans"))
    if not package.pieces:
        issues.append(ValidationIssue("pieces.required", "Debe existir al menos una pieza", "pieces"))

    objective_ids = {item.objective_id for item in package.objectives}
    audience_ids = {item.audience_id for item in package.audiences}
    pillar_ids = {item.pillar_id for item in package.pillars}
    piece_ids = {item.piece_id for item in package.pieces}
    channels = {item.channel.strip().casefold() for item in package.channel_plans}

    if len(piece_ids) != len(package.pieces):
        issues.append(ValidationIssue("pieces.duplicate_id", "Hay piece_id duplicados", "pieces"))

    for index, piece in enumerate(package.pieces):
        path = f"pieces[{index}]"
        if not piece.title.strip():
            issues.append(ValidationIssue("piece.title.required", "El título es obligatorio", f"{path}.title"))
        if piece.objective_id not in objective_ids:
            issues.append(ValidationIssue("piece.objective.unknown", "objective_id no existe", f"{path}.objective_id"))
        if piece.audience_id not in audience_ids:
            issues.append(ValidationIssue("piece.audience.unknown", "audience_id no existe", f"{path}.audience_id"))
        if piece.pillar_id not in pillar_ids:
            issues.append(ValidationIssue("piece.pillar.unknown", "pillar_id no existe", f"{path}.pillar_id"))
        if piece.channel.strip().casefold() not in channels:
            issues.append(ValidationIssue("piece.channel.unknown", "La pieza no tiene ChannelPlan", f"{path}.channel"))
        if piece.status in {ContentStatus.SCHEDULED, ContentStatus.PUBLISHED} and not piece.publish_date:
            issues.append(ValidationIssue("piece.publish_date.required", "La fecha es obligatoria para este estado", f"{path}.publish_date"))

    calendar_start = date.fromisoformat(package.calendar.start_date)
    calendar_end = date.fromisoformat(package.calendar.end_date)
    scheduled_piece_ids: set[str] = set()
    for index, slot in enumerate(package.calendar.slots):
        path = f"calendar.slots[{index}]"
        slot_date = date.fromisoformat(slot.publish_date)
        if slot.piece_id not in piece_ids:
            issues.append(ValidationIssue("slot.piece.unknown", "piece_id no existe", f"{path}.piece_id"))
        if not calendar_start <= slot_date <= calendar_end:
            issues.append(ValidationIssue("slot.date.out_of_range", "La fecha está fuera del calendario", f"{path}.publish_date"))
        if slot.piece_id in scheduled_piece_ids:
            issues.append(ValidationIssue("slot.piece.duplicate", "Una pieza aparece en más de un slot", f"{path}.piece_id", "warning"))
        scheduled_piece_ids.add(slot.piece_id)

    for index, piece in enumerate(package.pieces):
        if piece.publish_date:
            matching = [slot for slot in package.calendar.slots if slot.piece_id == piece.piece_id]
            if not matching:
                issues.append(ValidationIssue("piece.calendar.missing", "La pieza tiene fecha pero no tiene slot", f"pieces[{index}].publish_date", "warning"))
            elif all(slot.publish_date != piece.publish_date for slot in matching):
                issues.append(ValidationIssue("piece.calendar.date_mismatch", "La fecha de la pieza no coincide con el slot", f"pieces[{index}].publish_date"))

    return tuple(issues)


def assert_valid_content_package(package: ContentPackage, *, include_warnings: bool = False) -> None:
    issues = validate_content_package(package)
    blocking = issues if include_warnings else tuple(issue for issue in issues if issue.severity == "error")
    if blocking:
        raise ContentDomainValidationError(blocking)
