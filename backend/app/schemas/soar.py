from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

class SoarRuleBase(BaseModel):
    name: str
    condition_logic: str = "AND"
    condition_config: List[Dict[str, Any]] = []

class SoarRuleCreate(SoarRuleBase):
    pass

class SoarRuleUpdate(BaseModel):
    name: Optional[str] = None
    condition_logic: Optional[str] = None
    condition_config: Optional[List[Dict[str, Any]]] = None

class SoarRuleOut(SoarRuleBase):
    id: uuid.UUID
    playbook_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

class SoarActionBase(BaseModel):
    name: str
    action_type: str
    step_order: int = 1
    config: Dict[str, Any] = {}

class SoarActionCreate(SoarActionBase):
    pass

class SoarActionUpdate(BaseModel):
    name: Optional[str] = None
    action_type: Optional[str] = None
    step_order: Optional[int] = None
    config: Optional[Dict[str, Any]] = None

class SoarActionOut(SoarActionBase):
    id: uuid.UUID
    playbook_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

class SoarPlaybookBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    execution_mode: str = "Auto"

class SoarPlaybookCreate(SoarPlaybookBase):
    rules: List[SoarRuleCreate] = []
    actions: List[SoarActionCreate] = []

class SoarPlaybookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    execution_mode: Optional[str] = None

class SoarPlaybookOut(SoarPlaybookBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    rules: List[SoarRuleOut] = []
    actions: List[SoarActionOut] = []

    class Config:
        from_attributes = True

class SoarLogOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    action_id: Optional[uuid.UUID]
    step_order: int
    status: str
    message: str
    request_payload: Optional[Dict[str, Any]]
    response_payload: Optional[Dict[str, Any]]
    timestamp: datetime

    class Config:
        from_attributes = True

class SoarApprovalOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    status: str
    requested_at: datetime
    decided_at: Optional[datetime]
    decided_by_id: Optional[uuid.UUID]

    class Config:
        from_attributes = True

class SoarRunOut(BaseModel):
    id: uuid.UUID
    playbook_id: uuid.UUID
    trigger_source: str
    trigger_data: Dict[str, Any]
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    approval: Optional[SoarApprovalOut] = None

    class Config:
        from_attributes = True
