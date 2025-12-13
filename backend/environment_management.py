"""
N8枢纽控制中心 - M3-07 环境变量管理模块
支持读取、设置、删除环境变量
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

class EnvironmentActionRequest(BaseModel):
    """环境变量操作请求"""
    device_id: str = Field(..., description="设备ID")
    action: str = Field(..., description="操作类型：get/set/delete/list")
    var_name: Optional[str] = Field(None, description="变量名称")
    var_value: Optional[str] = Field(None, description="变量值（set操作时必需）")
    scope: Optional[str] = Field("user", description="作用域：user/system（Windows）或 session/permanent（Linux/macOS）")


class EnvironmentActionResponse(BaseModel):
    """环境变量操作响应"""
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

class EnvironmentManagementManager:
    """环境变量管理管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = sqlalchemy.create_engine(database_url)
    
    async def create_environment_action(
        self,
        device_id: str,
        action: str,
        var_name: Optional[str] = None,
        var_value: Optional[str] = None,
        scope: str = "user"
    ) -> dict:
        """创建环境变量操作"""
        # 验证操作类型
        valid_actions = ['get', 'set', 'delete', 'list']
        if action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}. Must be one of: {', '.join(valid_actions)}"
            )
        
        # 检查设备是否存在
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT device_id, status FROM devices WHERE device_id = :device_id"),
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
        
        # 生成操作ID
        action_id = f"env-{uuid.uuid4().hex[:16]}"
        created_at = datetime.now()
        
        # 创建环境变量操作任务
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO environment_actions 
                    (action_id, device_id, action, var_name, var_value, scope, status, created_at)
                    VALUES (:action_id, :device_id, :action, :var_name, :var_value, :scope, :status, :created_at)
                """),
                {
                    "action_id": action_id,
                    "device_id": device_id,
                    "action": action,
                    "var_name": var_name,
                    "var_value": var_value,
                    "scope": scope,
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
            "message": f"Environment action '{action}' scheduled. Agent will execute it.",
            "created_at": created_at.isoformat()
        }


# 全局管理器实例
_environment_manager: Optional[EnvironmentManagementManager] = None


def get_environment_manager() -> EnvironmentManagementManager:
    """获取环境变量管理管理器实例"""
    if _environment_manager is None:
        raise RuntimeError("EnvironmentManagementManager not initialized")
    return _environment_manager


def init_environment_manager(database_url: str):
    """初始化环境变量管理管理器"""
    global _environment_manager
    _environment_manager = EnvironmentManagementManager(database_url)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/environment", response_model=EnvironmentActionResponse)
async def environment_action(
    request: EnvironmentActionRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    执行环境变量操作
    
    **权限**: command:execute
    
    **功能**:
    - 获取环境变量（get）
    - 设置环境变量（set）
    - 删除环境变量（delete）
    - 列出所有环境变量（list）
    
    **作用域**:
    - Windows:
      - user: 用户级环境变量
      - system: 系统级环境变量（需要管理员权限）
    - Linux/macOS:
      - session: 当前会话
      - permanent: 永久（写入~/.bashrc或/etc/environment）
    
    **注意事项**:
    - 系统级环境变量需要管理员权限
    - 永久环境变量需要重新登录或重启shell生效
    - PATH等特殊变量建议追加而不是覆盖
    """
    manager = get_environment_manager()
    
    result = await manager.create_environment_action(
        device_id=request.device_id,
        action=request.action,
        var_name=request.var_name,
        var_value=request.var_value,
        scope=request.scope or "user"
    )
    
    return EnvironmentActionResponse(**result)
