from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Approval, AgentRun
from app.core.di import get_db_session


class ApprovalService:
    """Service for managing human approvals and audit logging."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def request_approval(
        self,
        run_id: UUID,
        action_type: str,
        action_data: dict,
        requested_by: UUID = None,
    ) -> Approval:
        """Request human approval for an action."""
        approval = Approval(
            run_id=run_id,
            action_type=action_type,
            action_data=action_data,
            status="pending",
            requested_by=requested_by,
        )
        self.db.add(approval)
        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def approve(self, approval_id: UUID, reviewed_by: UUID) -> Approval:
        """Approve a pending action."""
        result = await self.db.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise ValueError("Approval not found")

        approval.status = "approved"
        approval.reviewed_by = reviewed_by
        approval.reviewed_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def reject(self, approval_id: UUID, reviewed_by: UUID, reason: str = None) -> Approval:
        """Reject a pending action."""
        result = await self.db.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise ValueError("Approval not found")

        approval.status = "rejected"
        approval.reviewed_by = reviewed_by
        approval.reviewed_at = datetime.utcnow()
        approval.rejection_reason = reason
        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def list_pending(self, user_id: UUID = None) -> List[Dict]:
        """List pending approvals."""
        query = select(Approval).where(Approval.status == "pending")
        if user_id:
            query = query.where(Approval.requested_by == user_id)

        result = await self.db.execute(query)
        approvals = result.scalars().all()
        return [
            {
                "id": str(a.id),
                "run_id": str(a.run_id),
                "action_type": a.action_type,
                "action_data": a.action_data,
                "status": a.status,
                "requested_by": str(a.requested_by) if a.requested_by else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ]

    async def get_audit_log(self, run_id: UUID = None, limit: int = 50) -> List[Dict]:
        """Get audit log of all approvals."""
        query = select(Approval).order_by(Approval.created_at.desc()).limit(limit)
        if run_id:
            query = query.where(Approval.run_id == run_id)

        result = await self.db.execute(query)
        approvals = result.scalars().all()
        return [
            {
                "id": str(a.id),
                "run_id": str(a.run_id),
                "action_type": a.action_type,
                "action_data": a.action_data,
                "status": a.status,
                "requested_by": str(a.requested_by) if a.requested_by else None,
                "reviewed_by": str(a.reviewed_by) if a.reviewed_by else None,
                "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
                "rejection_reason": a.rejection_reason,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ]


async def get_approval_service(
    db: AsyncSession = Depends(get_db_session),
) -> ApprovalService:
    return ApprovalService(db)