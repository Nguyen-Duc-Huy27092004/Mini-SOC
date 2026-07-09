import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_active_user
from app.models.soar import SoarPlaybook, SoarRule, SoarAction, SoarRun, SoarLog, SoarApproval
from app.models.user import User
from app.schemas.soar import (
    SoarPlaybookCreate, SoarPlaybookOut, SoarPlaybookUpdate,
    SoarRuleCreate, SoarActionCreate, SoarRunOut, SoarLogOut, SoarApprovalOut
)
from app.soar.playbook_engine import PlaybookEngine

router = APIRouter()

# -----------------------------------------
# Playbooks
# -----------------------------------------

@router.get("/playbooks", response_model=List[SoarPlaybookOut])
async def list_playbooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    stmt = select(SoarPlaybook).options(selectinload(SoarPlaybook.rules), selectinload(SoarPlaybook.actions))
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/playbooks", response_model=SoarPlaybookOut, status_code=status.HTTP_201_CREATED)
async def create_playbook(
    data: SoarPlaybookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    pb = SoarPlaybook(
        name=data.name,
        description=data.description,
        is_active=data.is_active,
        execution_mode=data.execution_mode
    )
    db.add(pb)
    await db.commit()
    await db.refresh(pb)

    for r in data.rules:
        db.add(SoarRule(playbook_id=pb.id, **r.model_dump()))
    for a in data.actions:
        db.add(SoarAction(playbook_id=pb.id, **a.model_dump()))

    await db.commit()
    await db.refresh(pb, ["rules", "actions"])
    return pb

# -----------------------------------------
# Runs & History
# -----------------------------------------

@router.get("/runs", response_model=List[SoarRunOut])
async def list_runs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    stmt = select(SoarRun).order_by(SoarRun.started_at.desc()).options(selectinload(SoarRun.approval))
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/runs/{run_id}/logs", response_model=List[SoarLogOut])
async def get_run_logs(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    stmt = select(SoarLog).where(SoarLog.run_id == run_id).order_by(SoarLog.timestamp)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/playbooks/{playbook_id}/run")
async def manual_trigger_playbook(
    playbook_id: uuid.UUID,
    trigger_data: dict,
    dry_run: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    playbook = await db.get(SoarPlaybook, playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    await db.refresh(playbook, ["actions"])
    engine = PlaybookEngine(db)
    # Manual run triggers regardless of rules
    await engine.trigger_playbook(playbook, trigger_source="manual", trigger_data=trigger_data, is_dry_run=dry_run)
    return {"message": "Playbook triggered manually", "dry_run": dry_run}

# -----------------------------------------
# Approvals
# -----------------------------------------

@router.get("/approvals", response_model=List[SoarApprovalOut])
async def list_approvals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    stmt = select(SoarApproval).where(SoarApproval.status == "Pending")
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: uuid.UUID,
    decision: str, # "Approved" or "Rejected"
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    approval = await db.get(SoarApproval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if decision not in ["Approved", "Rejected"]:
        raise HTTPException(status_code=400, detail="Invalid decision")

    approval.status = decision
    import datetime
    approval.decided_at = datetime.datetime.now(datetime.timezone.utc)
    approval.decided_by_id = current_user.id
    
    run = await db.get(SoarRun, approval.run_id)
    
    if decision == "Approved":
        engine = PlaybookEngine(db)
        # We need to run it in background to not block response
        import asyncio
        asyncio.create_task(engine.execute_run(run.id))
    else:
        run.status = "Failed" # Rejected counts as fail/stop
        
    await db.commit()
    return {"message": f"Approval {decision}"}
