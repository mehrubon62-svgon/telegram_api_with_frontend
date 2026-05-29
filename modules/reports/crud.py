"""CRUD жалоб."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import (
    Report,
    ReportTargetType,
    ReportReason,
    User,
    Message,
    Chat,
    Story,
)


def utc() -> datetime:
    return datetime.now(timezone.utc)


def target_exists(db: Session, target_type: ReportTargetType, target_id: int) -> bool:
    if target_type == ReportTargetType.user:
        return db.query(User).filter(User.id == target_id).first() is not None
    if target_type == ReportTargetType.message:
        return db.query(Message).filter(Message.id == target_id).first() is not None
    if target_type == ReportTargetType.chat:
        return db.query(Chat).filter(Chat.id == target_id).first() is not None
    if target_type == ReportTargetType.story:
        return db.query(Story).filter(Story.id == target_id).first() is not None
    return False


def create_report(
    db: Session,
    *,
    reporter_id: int,
    target_type: ReportTargetType,
    target_id: int,
    reason: ReportReason,
    comment: str | None = None,
) -> Report:
    report = Report(
        reporter_id=reporter_id,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        comment=comment,
    )
    db.add(report)
    return report


def get_report(db: Session, report_id: int) -> Report | None:
    return db.query(Report).filter(Report.id == report_id).first()


def list_my_reports(db: Session, reporter_id: int, limit: int = 50) -> list[Report]:
    return (
        db.query(Report)
        .filter(Report.reporter_id == reporter_id)
        .order_by(Report.id.desc())
        .limit(limit)
        .all()
    )


def list_pending_reports(
    db: Session,
    *,
    target_type: ReportTargetType | None = None,
    reason: ReportReason | None = None,
    limit: int = 100,
    before_id: int | None = None,
) -> list[Report]:
    q = db.query(Report).filter(Report.status == "pending")
    if target_type:
        q = q.filter(Report.target_type == target_type)
    if reason:
        q = q.filter(Report.reason == reason)
    if before_id is not None:
        q = q.filter(Report.id < before_id)
    return q.order_by(Report.id.desc()).limit(limit).all()


def review_report(
    db: Session,
    report: Report,
    *,
    reviewer_id: int,
    action: str,
) -> Report:
    """`action` ∈ {reviewed, actioned, dismissed}."""
    report.status = action
    report.reviewed_at = utc()
    report.reviewed_by_id = reviewer_id
    return report


def count_reports_for_target(
    db: Session,
    target_type: ReportTargetType,
    target_id: int,
) -> int:
    return (
        db.query(Report)
        .filter(Report.target_type == target_type, Report.target_id == target_id)
        .count()
    )
