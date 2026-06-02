from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    role: str
    warehouse_id: Optional[int]
    is_active: bool
    is_locked: bool

    model_config = ConfigDict(from_attributes=True)


class SyncLogOut(BaseModel):
    id: int
    warehouse_id: int
    triggered_by: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    status: str
    records_updated: int
    error_message: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class WarehouseStatusOut(BaseModel):
    id: int
    code: str
    name: str
    is_online: bool
    last_seen: Optional[datetime]
    agent_url: str

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryOut(BaseModel):
    id: int
    session_id: str
    question: str
    response: str
    warehouses_context: Optional[str]
    timestamp: datetime
    response_time_ms: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class StockOut(BaseModel):
    id: int
    warehouse_id: int
    product_code: str
    product_name: str
    category: Optional[str]
    quantity: int
    min_quantity: int
    unit: str
    location_in_warehouse: Optional[str]
    status: str
    last_synced: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class StockSerialOut(BaseModel):
    id: int
    warehouse_id: int
    product_code: str
    serial_number: str
    product_name: str
    category: Optional[str]
    location_in_warehouse: Optional[str]
    status: str
    last_synced: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class StockUpdateRequest(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = None
    location_in_warehouse: Optional[str] = None
    min_quantity: Optional[int] = Field(default=None, ge=0)


class StockSerialUpdateRequest(BaseModel):
    status: Optional[str] = None
    location_in_warehouse: Optional[str] = None


class NotificationOut(BaseModel):
    id: int
    type: str
    message: str
    related_user_id: Optional[int]
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    role_id: int
    warehouse_id: Optional[int] = None


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    is_active: Optional[bool] = None


class PasswordResetRequest(BaseModel):
    new_password: str


class CrmNoteOut(BaseModel):
    id: int
    user_id: int
    content: str
    related_to: Optional[str]
    created_at: datetime
    modified_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class CrmNoteCreateRequest(BaseModel):
    content: str
    related_to: Optional[str] = None


class CrmNoteUpdateRequest(BaseModel):
    content: str
