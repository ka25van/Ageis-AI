from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.agent import Approval
from app.services.approval_service import ApprovalService, get_approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/{run_id}")
async def request_approval(
    run_id: UUID,
    action_type: str,
    action_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    service: ApprovalService = Depends(get_approval_service),
):
    approval = await service.request_approval(run_id, action_type, action_data, current_user.id)
    return {
        "id": str(approval.id),
        "run_id": str(approval.run_id),
        "action_type": approval.action_type,
        "status": approval.status,
        "requested_by": str(approval.requested_by),
        "created_at": approval.created_at.isoformat(),
    }


@router.post("/{approval_id}/approve")
async def approve(
    approval_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    service: ApprovalService = Depends(get_approval_service),
):
    approval = await service.approve(approval_id, current_user.id)
    return {"status": "approved", "id": str(approval.id)}


@router.post("/{approval_id}/reject")
async def reject(
    approval_id: UUID,
    reason: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    service: ApprovalService = Depends(get_approval_service),
):
    approval = await service.reject(approval_id, current_user.id, reason)
    return {"status": "rejected", "id": str(approval.id), "reason": reason}


@router.get("/pending")
async def list_pending(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    service: ApprovalService = Depends(get_approval_service),
):
    approvals = await service.list_pending(current_user.id)
    return {"approvals": approvals, "count": len(approvals)}


@router.get("/audit")
async def get_audit_log(
    run_id: UUID = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
    service: ApprovalService = Depends(get_approval_service),
):
    log = await service.get_audit_log(run_id, limit)
    return {"audit_log": log, "count": len(log)}