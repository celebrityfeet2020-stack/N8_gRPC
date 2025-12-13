"""
N8枢纽控制中心 - M3-06 注册表编辑模块（Windows）
支持读取、写入、删除注册表键值
"""

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import sqlalchemy
from sqlalchemy import text

# 导入认证中间件
from auth_middleware import require_auth


# ============================================================
# Pydantic Models
# ============================================================

class RegistryActionRequest(BaseModel):
    """注册表操作请求"""
    device_id: str = Field(..., description="设备ID")
    action: str = Field(..., description="操作类型：read/write/delete")
    key_path: str = Field(..., description="注册表键路径，如HKEY_LOCAL_MACHINE\\SOFTWARE\\...")
    value_name: Optional[str] = Field(None, description="值名称")
    value_data: Optional[str] = Field(None, description="值数据（write操作时必需）")
    value_type: Optional[str] = Field("REG_SZ", description="值类型：REG_SZ/REG_DWORD/REG_BINARY等")


class RegistryActionResponse(BaseModel):
    """注册表操作响应"""
    action_id: str = Field(..., description="操作ID")
    device_id: str = Field(..., description="设备ID")
    action: str = Field(..., description="操作类型")
    status: str = Field(..., description="状态：pending/completed/failed")
    created_at: str = Field(..., description="创建时间")


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/api/v1/commands", tags=["M3-CommandExecution"])


# ============================================================
# Database Manager
# ============================================================

class RegistryManagementManager:
    """注册表管理管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = sqlalchemy.create_engine(database_url)
    
    async def create_registry_action(
        self,
        device_id: str,
        action: str,
        key_path: str,
        value_name: Optional[str] = None,
        value_data: Optional[str] = None,
        value_type: str = "REG_SZ"
    ) -> dict:
        """创建注册表操作"""
        # 验证操作类型
        valid_actions = ['read', 'write', 'delete', 'create_key', 'delete_key']
        if action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}. Must be one of: {', '.join(valid_actions)}"
            )
        
        # 检查设备是否存在且为Windows
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT device_id, status, os_type FROM devices WHERE device_id = :device_id"),
                {"device_id": device_id}
            )
            device = result.fetchone()
            
            if not device:
                raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
            
            if device[1] != 'online':
                raise HTTPException(
                    status_code=400,
                    detail=f"Device is not online: {device_id} (status: {device[1]})"
                )
            
            if device[2] != 'windows':
                raise HTTPException(
                    status_code=400,
                    detail=f"Registry operations are only supported on Windows. Device OS: {device[2]}"
                )
        
        # 生成操作ID
        action_id = f"registry-{uuid.uuid4().hex[:16]}"
        created_at = datetime.now()
        
        # 创建注册表操作任务
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO registry_actions 
                    (action_id, device_id, action, key_path, value_name, value_data, 
                     value_type, status, created_at)
                    VALUES (:action_id, :device_id, :action, :key_path, :value_name, :value_data,
                            :value_type, :status, :created_at)
                """),
                {
                    "action_id": action_id,
                    "device_id": device_id,
                    "action": action,
                    "key_path": key_path,
                    "value_name": value_name,
                    "value_data": value_data,
                    "value_type": value_type,
                    "status": "pending",
                    "created_at": created_at
                }
            )
            conn.commit()
        
        return {
            "action_id": action_id,
            "device_id": device_id,
            "action": action,
            "status": "pending",
            "message": f"Registry action '{action}' scheduled. Agent will execute it.",
            "created_at": created_at.isoformat()
        }


# 全局管理器实例
_registry_manager: Optional[RegistryManagementManager] = None


def get_registry_manager() -> RegistryManagementManager:
    """获取注册表管理管理器实例"""
    if _registry_manager is None:
        raise RuntimeError("RegistryManagementManager not initialized")
    return _registry_manager


def init_registry_manager(database_url: str):
    """初始化注册表管理管理器"""
    global _registry_manager
    _registry_manager = RegistryManagementManager(database_url)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/registry", response_model=RegistryActionResponse)
async def registry_action(
    request: RegistryActionRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    执行注册表操作（仅Windows）
    
    **权限**: command:execute
    
    **功能**:
    - 读取注册表值（read）
    - 写入注册表值（write）
    - 删除注册表值（delete）
    - 创建注册表键（create_key）
    - 删除注册表键（delete_key）
    
    **注册表根键**:
    - HKEY_LOCAL_MACHINE (HKLM)
    - HKEY_CURRENT_USER (HKCU)
    - HKEY_CLASSES_ROOT (HKCR)
    - HKEY_USERS (HKU)
    - HKEY_CURRENT_CONFIG (HKCC)
    
    **值类型**:
    - REG_SZ: 字符串
    - REG_DWORD: 32位整数
    - REG_QWORD: 64位整数
    - REG_BINARY: 二进制数据
    - REG_MULTI_SZ: 多字符串
    - REG_EXPAND_SZ: 可扩展字符串
    
    **注意事项**:
    - 仅支持Windows系统
    - 需要管理员权限
    - 修改注册表可能影响系统稳定性
    """
    manager = get_registry_manager()
    
    result = await manager.create_registry_action(
        device_id=request.device_id,
        action=request.action,
        key_path=request.key_path,
        value_name=request.value_name,
        value_data=request.value_data,
        value_type=request.value_type or "REG_SZ"
    )
    
    return RegistryActionResponse(**result)
