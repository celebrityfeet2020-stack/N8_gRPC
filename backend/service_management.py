"""
N8枢纽控制中心 - M3-05 服务管理模块
支持启动、停止、重启、查询服务状态
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

class ServiceActionRequest(BaseModel):
    """服务操作请求"""
    device_id: str = Field(..., description="设备ID")
    service_name: str = Field(..., description="服务名称")
    action: str = Field(..., description="操作类型：start/stop/restart/status")


class ServiceActionResponse(BaseModel):
    """服务操作响应"""
    action_id: str = Field(..., description="操作ID")
    device_id: str = Field(..., description="设备ID")
    service_name: str = Field(..., description="服务名称")
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

class ServiceManagementManager:
    """服务管理管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = sqlalchemy.create_engine(database_url)
    
    async def create_service_action(
        self,
        device_id: str,
        service_name: str,
        action: str
    ) -> dict:
        """创建服务操作"""
        # 验证操作类型
        valid_actions = ['start', 'stop', 'restart', 'status', 'enable', 'disable']
        if action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}. Must be one of: {', '.join(valid_actions)}"
            )
        
        # 生成操作ID
        action_id = f"service-{uuid.uuid4().hex[:16]}"
        
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
        
        # 创建服务操作任务
        created_at = datetime.now()
        
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO service_actions 
                    (action_id, device_id, service_name, action, status, created_at)
                    VALUES (:action_id, :device_id, :service_name, :action, :status, :created_at)
                """),
                {
                    "action_id": action_id,
                    "device_id": device_id,
                    "service_name": service_name,
                    "action": action,
                    "status": "pending",
                    "created_at": created_at
                }
            )
            conn.commit()
        
        return {
            "action_id": action_id,
            "device_id": device_id,
            "service_name": service_name,
            "action": action,
            "status": "pending",
            "message": f"Service action '{action}' on '{service_name}' scheduled. Agent will execute it.",
            "created_at": created_at.isoformat()
        }


# 全局管理器实例
_service_manager: Optional[ServiceManagementManager] = None


def get_service_manager() -> ServiceManagementManager:
    """获取服务管理管理器实例"""
    if _service_manager is None:
        raise RuntimeError("ServiceManagementManager not initialized")
    return _service_manager


def init_service_manager(database_url: str):
    """初始化服务管理管理器"""
    global _service_manager
    _service_manager = ServiceManagementManager(database_url)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/service", response_model=ServiceActionResponse)
async def service_action(
    request: ServiceActionRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    执行服务操作
    
    **权限**: command:execute
    
    **功能**:
    - 启动服务（start）
    - 停止服务（stop）
    - 重启服务（restart）
    - 查询状态（status）
    - 启用服务（enable）- 开机自启
    - 禁用服务（disable）- 禁止开机自启
    
    **平台支持**:
    - Windows: sc.exe / net.exe
    - Linux: systemctl / service
    - macOS: launchctl
    """
    manager = get_service_manager()
    
    result = await manager.create_service_action(
        device_id=request.device_id,
        service_name=request.service_name,
        action=request.action
    )
    
    return ServiceActionResponse(**result)
