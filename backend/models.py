"""
N8 gRPC Control Center - Database Models
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Device(Base):
    """设备表"""
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(100), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    os_type = Column(String(50), nullable=False)  # linux/darwin/windows
    os_version = Column(String(255))
    agent_version = Column(String(50))
    
    # 认证
    token = Column(String(255), unique=True, nullable=False)
    psk_hash = Column(String(255), nullable=False)
    
    # 状态
    status = Column(String(20), default="offline")  # online/offline
    last_seen_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 系统信息
    cpu_usage = Column(Float, default=0.0)
    memory_usage = Column(Float, default=0.0)
    disk_usage = Column(Float, default=0.0)
    uptime = Column(Integer, default=0)
    running_services = Column(JSON, default=list)
    
    # 元数据
    metadata = Column(JSON, default=dict)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_device_status', 'status'),
        Index('idx_device_last_seen', 'last_seen_at'),
    )


class Command(Base):
    """命令表"""
    __tablename__ = "commands"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    command_id = Column(String(100), unique=True, nullable=False, index=True)
    device_id = Column(String(100), nullable=False, index=True)
    
    # 命令内容
    command_type = Column(String(50), nullable=False)  # exec/upload/download/restart
    payload = Column(Text, nullable=False)  # JSON格式
    timeout = Column(Integer, default=300)
    
    # 状态
    status = Column(String(20), default="pending")  # pending/running/completed/failed
    
    # 执行结果
    success = Column(Boolean, default=False)
    stdout = Column(Text)
    stderr = Column(Text)
    exit_code = Column(Integer)
    executed_at = Column(DateTime)
    duration_ms = Column(Integer)
    
    # 创建信息
    created_by = Column(String(100))  # 创建者（用户ID或系统）
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_command_device_status', 'device_id', 'status'),
        Index('idx_command_created', 'created_at'),
    )


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(100), index=True)
    action = Column(String(100), nullable=False)  # register/heartbeat/execute/etc
    details = Column(JSON)
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_audit_device_action', 'device_id', 'action'),
    )
