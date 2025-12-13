"""
N8 Control Center - 合并数据库模型
包含：账户系统 + 设备控制
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, Index, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import secrets
import enum

Base = declarative_base()


# ============================================
# 枚举类型
# ============================================

class UserRole(str, enum.Enum):
    """用户角色"""
    ADMIN = "ADMIN"          # 管理员
    OPERATOR = "OPERATOR"    # 操作员（可以执行命令）
    VIEWER = "VIEWER"        # 只读用户（只能查看）
    AGENT = "AGENT"          # AI智能体


class DevicePermission(str, enum.Enum):
    """设备权限"""
    READ = "READ"            # 只读（查看设备状态）
    EXECUTE = "EXECUTE"      # 执行命令
    MANAGE = "MANAGE"        # 管理设备（注册/删除）


# ============================================
# 用户和认证模型
# ============================================

class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(Text)  # 用户描述
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    api_keys = relationship('APIKey', back_populates='user', cascade='all, delete-orphan')
    audit_logs = relationship('AuditLog', back_populates='user')
    user_device_permissions = relationship('UserDevicePermission', back_populates='user', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('idx_user_role', 'role'),
        Index('idx_user_active', 'is_active'),
    )


class APIKey(Base):
    """API密钥表"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    key = Column(String(64), nullable=False, unique=True, index=True)  # sk-xxx格式
    name = Column(String(255), nullable=False)  # 密钥名称
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # 过期时间
    last_used_at = Column(DateTime, nullable=True)  # 最后使用时间
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship('User', back_populates='api_keys')
    
    @staticmethod
    def generate_key() -> str:
        """生成一个新的API Key"""
        return f"sk-{secrets.token_urlsafe(32)}"
    
    def is_expired(self) -> bool:
        """检查密钥是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    __table_args__ = (
        Index('idx_apikey_active', 'is_active'),
    )


# ============================================
# 设备管理模型
# ============================================

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
    meta_data = Column(JSON, default=dict)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    commands = relationship('Command', back_populates='device')
    user_device_permissions = relationship('UserDevicePermission', back_populates='device', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('idx_device_status', 'status'),
        Index('idx_device_last_seen', 'last_seen_at'),
    )


class Command(Base):
    """命令表"""
    __tablename__ = "commands"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    command_id = Column(String(100), unique=True, nullable=False, index=True)
    device_id = Column(String(100), ForeignKey('devices.device_id'), nullable=False, index=True)
    
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
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # 哪个用户创建的
    created_by = Column(String(100))  # 兼容旧版本（用户名或"system"）
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    device = relationship('Device', back_populates='commands')
    creator = relationship('User', foreign_keys=[created_by_user_id])
    
    __table_args__ = (
        Index('idx_command_device_status', 'device_id', 'status'),
        Index('idx_command_created', 'created_at'),
    )


# ============================================
# 权限管理模型
# ============================================

class UserDevicePermission(Base):
    """用户设备权限表"""
    __tablename__ = "user_device_permissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    device_id = Column(String(100), ForeignKey('devices.device_id'), nullable=False, index=True)
    permission = Column(SQLEnum(DevicePermission), nullable=False)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship('User', back_populates='user_device_permissions')
    device = relationship('Device', back_populates='user_device_permissions')
    
    __table_args__ = (
        Index('idx_user_device', 'user_id', 'device_id'),
    )


# ============================================
# 审计日志模型
# ============================================

class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    device_id = Column(String(100), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # 操作类型
    resource_type = Column(String(50), nullable=False)  # 资源类型
    resource_id = Column(String(100), nullable=True)  # 资源ID
    details = Column(JSON)  # 详细信息
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    status_code = Column(Integer)
    created_at = Column(DateTime, default=func.now(), index=True)
    
    # 关系
    user = relationship('User', back_populates='audit_logs')
    
    __table_args__ = (
        Index('idx_audit_device_action', 'device_id', 'action'),
        Index('idx_audit_user_action', 'user_id', 'action'),
    )
