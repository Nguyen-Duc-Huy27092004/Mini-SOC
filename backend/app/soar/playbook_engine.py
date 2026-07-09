import asyncio
from typing import Any, Dict, List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.soar import SoarPlaybook, SoarRun, SoarLog, SoarApproval
from app.soar.rule_engine import RuleEngine
from app.soar.action_engine import ActionEngine
from app.soar.retry_engine import RetryEngine

logger = structlog.get_logger()

class PlaybookEngine:
    """
    Coordinates evaluation of playbooks and execution of their actions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_trigger(self, trigger_source: str, trigger_data: Dict[str, Any]):
        """
        Evaluate all active playbooks against a trigger event.
        """
        logger.info("soar_processing_trigger", source=trigger_source)
        
        # Fetch active playbooks with rules and actions
        stmt = select(SoarPlaybook).where(SoarPlaybook.is_active == True)
        result = await self.db.execute(stmt)
        playbooks = result.scalars().unique().all() # Assuming joinedload or lazyload works based on configuration, but best is to explicit load if needed.
        # Note: In a real app we might need to eagerly load rules and actions.
        # For simplicity, assuming they are accessible via async lazy loading or joinedload.

        for playbook in playbooks:
            # We must load rules, so better fetch them explicitly if lazy loading async fails
            await self.db.refresh(playbook, ["rules", "actions"])

            # 1. Match Rules
            is_match = RuleEngine.evaluate(playbook.rules, trigger_data)
            
            if is_match:
                logger.info("soar_playbook_triggered", playbook_id=str(playbook.id), name=playbook.name)
                await self.trigger_playbook(playbook, trigger_source, trigger_data)

    async def trigger_playbook(self, playbook: SoarPlaybook, trigger_source: str, trigger_data: Dict[str, Any], is_dry_run: bool = False):
        """
        Execute a playbook based on its execution mode.
        If is_dry_run is True, simulates the execution without side effects.
        """
        if is_dry_run:
            logger.info("soar_dry_run_started", playbook=playbook.name)
            await self.execute_run(None, playbook, trigger_data, is_dry_run=True)
            return
            
        # Create a run record
        run = SoarRun(
            playbook_id=playbook.id,
            trigger_source=trigger_source,
            trigger_data=trigger_data,
            status="Running" if playbook.execution_mode == "Auto" else "Pending Approval"
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        if playbook.execution_mode == "Need Approval":
            approval = SoarApproval(run_id=run.id, status="Pending")
            self.db.add(approval)
            await self.db.commit()
            logger.info("soar_playbook_needs_approval", run_id=str(run.id))
            return # Pause execution until approved

        # Execute Auto
        await self.execute_run(run.id, playbook, trigger_data)

    async def execute_run(self, run_id: Any, playbook: SoarPlaybook, trigger_data: Dict[str, Any], is_dry_run: bool = False):
        """
        Executes actions for a given run sequentially.
        """
        if not is_dry_run:
            run = await self.db.get(SoarRun, run_id)
            if not run:
                return
            
            run.status = "Running"
            await self.db.commit()

        # Load actions if not already loaded (for dry run they might be)
        if not is_dry_run:
            await self.db.refresh(playbook, ["actions"])

        actions = sorted(playbook.actions, key=lambda a: a.step_order)
        all_success = True

        for action in actions:
            logger.info("soar_executing_action", run_id=str(run_id) if run_id else "DRY_RUN", action_name=action.name, is_dry_run=is_dry_run)
            
            if is_dry_run:
                # Simulate success
                logger.info("soar_dry_run_simulated_action", action_type=action.action_type, config=action.config)
                continue
            
            # Use retry engine
            result = await RetryEngine.execute_with_retry(
                ActionEngine.execute_action,
                max_retries=3,
                base_delay=1.0,
                action_type=action.action_type,
                config=action.config,
                trigger_data=trigger_data
            )
            
            if not is_dry_run:
                # Log action
                log = SoarLog(
                    run_id=run.id,
                    action_id=action.id,
                    step_order=action.step_order,
                    status="Success" if result and result.success else "Failed",
                    message=result.message if result else "Action execution failed completely",
                    request_payload=action.config,
                    response_payload=result.response_payload if result else {}
                )
                self.db.add(log)
                await self.db.commit()

            if not result or not result.success:
                all_success = False
                break # Stop execution on first failure

        if not is_dry_run:
            import datetime
            run.status = "Success" if all_success else "Failed"
            run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await self.db.commit()
            logger.info("soar_run_completed", run_id=str(run.id), status=run.status)
