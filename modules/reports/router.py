"""HTTP API жалоб.

  • POST   /reports             — пожаловаться (любой пользователь)
  • GET    /reports/my          — свои жалобы
  • GET    /reports             — pending очередь (только админ)
  • GET    /reports/{id}        — деталь (админ или автор)
  • POST   /reports/{id}/review — модерация (админ)
  • GET    /reports/target-count?... — сколько раз репортили цель (админ)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models import get_db, User, ReportTargetType, ReportReason, RoleEnum
from dependencies import get_current_user, require_admin

from modules.reports import crud
from modules.reports.schemas import ReportCreate, ReportOut, ReportDecision


router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("", response_model=ReportOut, status_code=201)
def create_report(
    data: ReportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not crud.target_exists(db, data.target_type, data.target_id):
        raise HTTPException(status_code=404, detail="Report target not found")

    # нельзя жаловаться на самого себя
    if data.target_type == ReportTargetType.user and data.target_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot report yourself")

    report = crud.create_report(
        db,
        reporter_id=user.id,
        target_type=data.target_type,
        target_id=data.target_id,
        reason=data.reason,
        comment=data.comment,
    )
    db.commit()
    db.refresh(report)
    return report


@router.get("/my", response_model=list[ReportOut])
def list_my_reports(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return crud.list_my_reports(db, user.id, limit=limit)


@router.get("", response_model=list[ReportOut])
def list_pending(
    target_type: ReportTargetType | None = Query(None),
    reason: ReportReason | None = Query(None),
    before_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return crud.list_pending_reports(
        db, target_type=target_type, reason=reason, limit=limit, before_id=before_id,
    )


@router.get("/target-count")
def target_count(
    target_type: ReportTargetType,
    target_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return {
        "target_type": target_type.value,
        "target_id": target_id,
        "count": crud.count_reports_for_target(db, target_type, target_id),
    }


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Not found")
    if user.role != RoleEnum.admin and report.reporter_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return report


@router.post("/{report_id}/review", response_model=ReportOut)
def review_report(
    report_id: int,
    data: ReportDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    report = crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Not found")
    if report.status != "pending":
        raise HTTPException(status_code=400, detail=f"Report already {report.status}")
    crud.review_report(db, report, reviewer_id=admin.id, action=data.action)
    db.commit()
    db.refresh(report)
    return report
