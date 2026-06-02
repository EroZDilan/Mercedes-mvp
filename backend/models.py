from datetime import datetime, UTC
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import relationship
from backend.database import Base


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    hierarchy_level = Column(Integer, nullable=False)
    system_prompt = Column(Text, nullable=False)
    users = relationship("User", back_populates="role")


class Warehouse(Base):
    __tablename__ = "warehouses"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    agent_url = Column(String, nullable=False, default="")
    agent_token = Column(String, nullable=False, default="")
    is_online = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=lambda: datetime.now(UTC))
    users = relationship("User", back_populates="warehouse")
    stock = relationship("Stock", back_populates="warehouse")
    stock_serial = relationship("StockSerial", back_populates="warehouse")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    failed_attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_login = Column(DateTime, nullable=True)
    role = relationship("Role", back_populates="users")
    warehouse = relationship("Warehouse", back_populates="users")
    sessions = relationship("Session", back_populates="user")


class Stock(Base):
    __tablename__ = "stock"
    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    product_code = Column(String, nullable=False)
    product_name = Column(String, nullable=False)
    category = Column(String)
    quantity = Column(Integer, nullable=False, default=0)
    min_quantity = Column(Integer, default=0)
    unit = Column(String, default="unidad")
    location_in_warehouse = Column(String)
    status = Column(String, default="disponible")
    last_synced = Column(DateTime, default=lambda: datetime.now(UTC))
    warehouse = relationship("Warehouse", back_populates="stock")


class StockSerial(Base):
    __tablename__ = "stock_serial"
    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    product_code = Column(String, nullable=False)
    serial_number = Column(String, unique=True, nullable=False)
    product_name = Column(String, nullable=False)
    category = Column(String)
    location_in_warehouse = Column(String)
    status = Column(String, default="disponible")
    last_synced = Column(DateTime, default=lambda: datetime.now(UTC))
    warehouse = relationship("Warehouse", back_populates="stock_serial")


class StockHistory(Base):
    __tablename__ = "stock_history"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer)
    product_type = Column(String)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    changed_by = Column(Integer, ForeignKey("users.id"))
    field_changed = Column(String)
    old_value = Column(String)
    new_value = Column(String)
    changed_at = Column(DateTime, default=lambda: datetime.now(UTC))


class SyncLog(Base):
    __tablename__ = "sync_log"
    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    triggered_by = Column(String, default="scheduler")
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    status = Column(String)
    records_updated = Column(Integer, default=0)
    error_message = Column(Text)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    jti = Column(String, unique=True, nullable=False)
    device_info = Column(String)
    ip_address = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime)
    is_revoked = Column(Boolean, default=False)
    user = relationship("User", back_populates="sessions")


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    warehouses_context = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    response_time_ms = Column(Integer)


class CrmNote(Base):
    __tablename__ = "crm_notes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    related_to = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    modified_at = Column(DateTime)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    related_user_id = Column(Integer)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    detail = Column(Text)
    ip_address = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
