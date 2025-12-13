"""
N8 Control Center - 安全的REST API (修复版)
包含：用户管理 + 设备控制 + API Key认证
修复：metadata字段别名映射问题
"""
from fastapi import FastAPI, HTTPException, Depends, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
import json
import hashlib
from sqlalchemy.orm import Session
from models_merged import (
    User, APIKey, Device, Command, AuditLog, UserDevicePermission,
    UserRole, DevicePermission
)
from grpc_server_secured import DatabaseManager, ControlCenterConfig
from auth import get_current_user, require_role, check_device_permission, log_audit

# ============================================
# FastAPI应用
# ============================================
app = FastAPI(
    title="N8 Control Center API",
    description="安全的设备控制中心REST API - 包含用户管理和API Key认证 (修复版)",
    version="2.0.1"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局配置和数据库管理器
config = ControlCenterConfig()
db_manager = DatabaseManager(config.database_url)

# ============================================
# 依赖注入
# ============================================
def get_db():
    """获取数据库会话"""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()

# ============================================
# Pydantic模型
# ============================================
# 用户相关
class UserCreate(BaseModel):
    username: str
    display_name: str
    role: UserRole
    description: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# API Key相关
class APIKeyCreate(BaseModel):
    name: str
    expires_in_days: Optional[int] = None  # None表示永不过期

class APIKeyResponse(BaseModel):
    id: int
    user_id: int
    key: str  # 只在创建时返回完整key
    name: str
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class APIKeyListResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_at: datetime
    key_preview: str  # 只显示前8个字符
    
    class Config:
        from_attributes = True

# 设备相关
class DeviceResponse(BaseModel):
    id: int
    device_id: str
    hostname: str
    os_type: str
    os_version: Optional[str]
    agent_version: Optional[str]
    status: str
    last_seen_at: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime: int
    running_services: List[str]
    # 🔧 修复：使用Field别名，从SQLAlchemy的meta_data读取到Pydantic的metadata
    metadata: dict = Field(alias="meta_data")
    created_at: datetime
    
    class Config:
        from_attributes = True
        # 允许通过别名填充字段
        populate_by_name = True

class DeviceUpdate(BaseModel):
    display_name: Optional[str] = None

# 命令相关
class CommandRequest(BaseModel):
    command_type: str
    payload: dict
    timeout: int = 300

class CommandResponse(BaseModel):
    id: int
    command_id: str
    device_id: str
    command_type: str
    status: str
    success: bool
    stdout: Optional[str]
    stderr: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime]
    duration_ms: Optional[int]
    
    class Config:
        from_attributes = True

# 权限相关
class PermissionGrant(BaseModel):
    device_id: str
    permission: DevicePermission

# ============================================
# 用户管理API
# ============================================
@app.get("/api/users/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user

# ============================================
# API Key管理API
# ============================================
@app.post("/api/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新的API Key"""
    # 生成Key
    key_str = APIKey.generate_key()
    
    # 计算过期时间
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
    
    new_key = APIKey(
        user_id=current_user.id,
        key=key_str,
        name=key_data.name,
        expires_at=expires_at
    )
    
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    
    # 记录审计日志
    await log_audit(
        request, current_user, "CREATE_API_KEY", "APIKey", str(new_key.id),
        200, {"name": key_data.name}, db
    )
    
    return new_key

@app.get("/api/api-keys", response_model=List[APIKeyListResponse])
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """列出当前用户的所有API Key"""
    keys = db.query(APIKey).filter_by(user_id=current_user.id).all()
    
    # 处理key预览
    result = []
    for k in keys:
        k_dict = k.__dict__.copy()
        k_dict['key_preview'] = f"{k.key[:8]}..."
        result.append(k_dict)
        
    return result

@app.delete("/api/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """撤销API Key"""
    key = db.query(APIKey).filter_by(id=key_id, user_id=current_user.id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API Key not found")
    
    db.delete(key)
    db.commit()
    
    # 记录审计日志
    await log_audit(
        request, current_user, "REVOKE_API_KEY", "APIKey", str(key_id),
        200, {}, db
    )
    
    return {"message": "API Key revoked successfully"}

# ============================================
# 设备管理API
# ============================================
@app.get("/api/devices", response_model=List[DeviceResponse])
def list_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取设备列表"""
    if current_user.role == UserRole.ADMIN:
        # 管理员可以看到所有设备
        devices = db.query(Device).all()
    else:
        # 普通用户只能看到有权限的设备
        # 获取用户有权限的设备ID列表
        perms = db.query(UserDevicePermission).filter_by(user_id=current_user.id).all()
        device_ids = [p.device_id for p in perms]
        devices = db.query(Device).filter(Device.device_id.in_(device_ids)).all()
    
    # 🔧 修复：手动构建响应，确保meta_data映射到metadata
    result = []
    for device in devices:
        device_dict = {
            "id": device.id,
            "device_id": device.device_id,
            "hostname": device.hostname,
            "os_type": device.os_type,
            "os_version": device.os_version,
            "agent_version": device.agent_version,
            "status": device.status,
            "last_seen_at": device.last_seen_at,
            "cpu_usage": device.cpu_usage,
            "memory_usage": device.memory_usage,
            "disk_usage": device.disk_usage,
            "uptime": device.uptime,
            "running_services": device.running_services,
            "metadata": device.meta_data,  # 映射meta_data到metadata
            "created_at": device.created_at,
        }
        result.append(DeviceResponse(**device_dict))
    
    return result

@app.get("/api/devices/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取设备详情"""
    # 权限检查
    if not check_device_permission(device_id, DevicePermission.READ, current_user, db):
        raise HTTPException(status_code=403, detail="No permission to access this device")
        
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 🔧 修复：手动构建响应
    device_dict = {
        "id": device.id,
        "device_id": device.device_id,
        "hostname": device.hostname,
        "os_type": device.os_type,
        "os_version": device.os_version,
        "agent_version": device.agent_version,
        "status": device.status,
        "last_seen_at": device.last_seen_at,
        "cpu_usage": device.cpu_usage,
        "memory_usage": device.memory_usage,
        "disk_usage": device.disk_usage,
        "uptime": device.uptime,
        "running_services": device.running_services,
        "metadata": device.meta_data,  # 映射meta_data到metadata
        "created_at": device.created_at,
    }
    
    return DeviceResponse(**device_dict)

@app.put("/api/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device_update: DeviceUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新设备信息（如重命名）"""
    # 权限检查：需要MANAGE权限
    if not check_device_permission(device_id, DevicePermission.MANAGE, current_user, db):
        raise HTTPException(status_code=403, detail="No permission to manage this device")
        
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device_update.display_name is not None:
        device.display_name = device_update.display_name
        
    db.commit()
    db.refresh(device)
    
    # 记录审计日志
    await log_audit(
        request, current_user, "UPDATE_DEVICE", "Device", device_id,
        200, {"display_name": device_update.display_name}, db
    )
    
    # 🔧 修复：手动构建响应
    device_dict = {
        "id": device.id,
        "device_id": device.device_id,
        "hostname": device.hostname,
        "os_type": device.os_type,
        "os_version": device.os_version,
        "agent_version": device.agent_version,
        "status": device.status,
        "last_seen_at": device.last_seen_at,
        "cpu_usage": device.cpu_usage,
        "memory_usage": device.memory_usage,
        "disk_usage": device.disk_usage,
        "uptime": device.uptime,
        "running_services": device.running_services,
        "metadata": device.meta_data,
        "created_at": device.created_at,
    }
    
    return DeviceResponse(**device_dict)

@app.post("/api/devices/{device_id}/execute", response_model=CommandResponse)
async def execute_command(
    device_id: str,
    command: CommandRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """向设备发送命令"""
    # 权限检查
    if not check_device_permission(device_id, DevicePermission.EXECUTE, current_user, db):
        raise HTTPException(status_code=403, detail="No permission to execute commands on this device")
        
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if device.status != "online":
        raise HTTPException(status_code=400, detail="Device is offline")
    
    # 创建命令记录
    cmd_id = str(uuid.uuid4())
    new_command = Command(
        command_id=cmd_id,
        device_id=device_id,
        command_type=command.command_type,
        payload=json.dumps(command.payload),
        timeout=command.timeout,
        status="pending",
        created_by_user_id=current_user.id,
        created_by=current_user.username
    )
    
    db.add(new_command)
    db.commit()
    db.refresh(new_command)
    
    # 记录审计日志
    await log_audit(
        request, current_user, "EXECUTE_COMMAND", "Command", cmd_id,
        200, {"command_type": command.command_type, "device_id": device_id}, db
    )
    
    return new_command

@app.get("/api/commands/{command_id}", response_model=CommandResponse)
def get_command(
    command_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取命令执行状态"""
    command = db.query(Command).filter_by(command_id=command_id).first()
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
        
    # 权限检查
    if not check_device_permission(command.device_id, DevicePermission.READ, current_user, db):
        raise HTTPException(status_code=403, detail="No permission to access this command")
        
    return command

@app.get("/api/devices/{device_id}/commands", response_model=List[CommandResponse])
def list_device_commands(
    device_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取设备的命令历史"""
    # 权限检查
    if not check_device_permission(device_id, DevicePermission.READ, current_user, db):
        raise HTTPException(status_code=403, detail="No permission to access this device")
        
    commands = db.query(Command).filter_by(device_id=device_id).order_by(Command.created_at.desc()).limit(limit).all()
    return commands

# ============================================
# 权限管理API（仅管理员）
# ============================================
@app.post("/api/users/{user_id}/permissions")
async def grant_permission(
    user_id: int,
    permission: PermissionGrant,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """授予用户设备权限"""
    # 检查用户是否存在
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 检查设备是否存在
    device = db.query(Device).filter_by(device_id=permission.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # 检查权限是否已存在
    existing = db.query(UserDevicePermission).filter_by(
        user_id=user_id,
        device_id=permission.device_id,
        permission=permission.permission
    ).first()
    
    if existing:
        return {"message": "Permission already exists"}
        
    # 创建权限
    new_perm = UserDevicePermission(
        user_id=user_id,
        device_id=permission.device_id,
        permission=permission.permission
    )
    
    db.add(new_perm)
    db.commit()
    
    # 记录审计日志
    await log_audit(
        request, current_user, "GRANT_PERMISSION", "Permission", f"{user_id}:{permission.device_id}",
        200, {"permission": permission.permission.value}, db
    )
    
    return {"message": "Permission granted successfully"}

@app.delete("/api/users/{user_id}/permissions/{device_id}/{permission}")
async def revoke_permission(
    user_id: int,
    device_id: str,
    permission: DevicePermission,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """撤销用户设备权限"""
    perm = db.query(UserDevicePermission).filter_by(
        user_id=user_id,
        device_id=device_id,
        permission=permission
    ).first()
    
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
        
    db.delete(perm)
    db.commit()
    
    # 记录审计日志
    await log_audit(
        request, current_user, "REVOKE_PERMISSION", "Permission", f"{user_id}:{device_id}",
        200, {"permission": permission.value}, db
    )
    
    return {"message": "Permission revoked successfully"}

# ============================================
# 健康检查
# ============================================
@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "healthy", "version": "2.0.1"}

@app.get("/")
def root():
    """根路径"""
    return {"message": "N8 Control Center API (修复版)", "version": "2.0.1", "docs": "/docs"}

# ============================================
# 启动服务
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
