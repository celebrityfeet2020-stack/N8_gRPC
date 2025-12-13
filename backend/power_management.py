"""
N8枢纽控制中心 - M3-04 电源管理模块
支持关机、重启、睡眠、休眠
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

class PowerActionRequest(BaseModel):
    """电源操作请求"""
    device_id: str = Field(..., description="设备ID")
    action: str = Field(..., description="操作类型：shutdown/reboot/sleep/hibernate/logout")
    force: Optional[bool] = Field(False, description="是否强制执行（不保存未保存的文件）")
    delay: Optional[int] = Field(0, description="延迟执行时间（秒），0表示立即执行")
    message: Optional[str] = Field(None, description="显示给用户的消息（Windows）")


class PowerActionResponse(BaseModel):
    """电源操作响应"""
    action_id: str = Field(..., description="操作ID")
    device_id: str = Field(..., description="设备ID")
    action: str = Field(..., description="操作类型")
    status: str = Field(..., description="状态：pending/completed/failed")
    scheduled_at: Optional[str] = Field(None, description="计划执行时间")
    created_at: str = Field(..., description="创建时间")


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/api/v1/commands", tags=["M3-CommandExecution"])


# ============================================================
# Database Manager
# ============================================================

class PowerManagementManager:
    """电源管理管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = sqlalchemy.create_engine(database_url)
    
    async def create_power_action(
        self,
        device_id: str,
        action: str,
        force: bool = False,
        delay: int = 0,
        message: Optional[str] = None
    ) -> dict:
        """
        创建电源操作
        
        Args:
            device_id: 设备ID
            action: 操作类型
            force: 是否强制执行
            delay: 延迟执行时间（秒）
            message: 显示给用户的消息
        
        Returns:
            操作结果字典
        """
        # 验证操作类型
        valid_actions = ['shutdown', 'reboot', 'sleep', 'hibernate', 'logout']
        if action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}. Must be one of: {', '.join(valid_actions)}"
            )
        
        # 生成操作ID
        action_id = f"power-{uuid.uuid4().hex[:16]}"
        
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
        
        # 计算计划执行时间
        created_at = datetime.now()
        scheduled_at = datetime.fromtimestamp(created_at.timestamp() + delay) if delay > 0 else created_at
        
        # 创建电源操作任务
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO power_actions 
                    (action_id, device_id, action, force, delay, message, status, 
                     scheduled_at, created_at)
                    VALUES (:action_id, :device_id, :action, :force, :delay, :message, :status,
                            :scheduled_at, :created_at)
                """),
                {
                    "action_id": action_id,
                    "device_id": device_id,
                    "action": action,
                    "force": force,
                    "delay": delay,
                    "message": message,
                    "status": "pending",
                    "scheduled_at": scheduled_at,
                    "created_at": created_at
                }
            )
            conn.commit()
        
        return {
            "action_id": action_id,
            "device_id": device_id,
            "action": action,
            "status": "pending",
            "scheduled_at": scheduled_at.isoformat() if delay > 0 else None,
            "message": f"Power action '{action}' scheduled. Agent will execute it.",
            "created_at": created_at.isoformat()
        }


# 全局管理器实例
_power_manager: Optional[PowerManagementManager] = None


def get_power_manager() -> PowerManagementManager:
    """获取电源管理管理器实例"""
    if _power_manager is None:
        raise RuntimeError("PowerManagementManager not initialized")
    return _power_manager


def init_power_manager(database_url: str):
    """初始化电源管理管理器"""
    global _power_manager
    _power_manager = PowerManagementManager(database_url)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/power", response_model=PowerActionResponse)
async def power_action(
    request: PowerActionRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    执行电源操作
    
    **权限**: command:execute
    
    **功能**:
    - 关机（shutdown）
    - 重启（reboot）
    - 睡眠（sleep）
    - 休眠（hibernate）
    - 注销（logout）
    
    **参数说明**:
    - force: 强制执行，不保存未保存的文件
    - delay: 延迟执行时间（秒），0表示立即执行
    - message: 显示给用户的消息（仅Windows）
    
    **注意事项**:
    - 设备必须在线
    - 操作执行后设备会离线
    - 建议使用delay参数给用户保存文件的时间
    - Windows下可以显示消息提示用户
    
    **平台支持**:
    - Windows: 全部支持
    - macOS: 支持shutdown/reboot/sleep/logout
    - Linux: 支持shutdown/reboot/suspend（sleep）
    """
    manager = get_power_manager()
    
    result = await manager.create_power_action(
        device_id=request.device_id,
        action=request.action,
        force=request.force or False,
        delay=request.delay or 0,
        message=request.message
    )
    
    return PowerActionResponse(**result)


@router.post("/power/cancel", response_model=dict)
async def cancel_power_action(
    action_id: str,
    auth_info: dict = Depends(require_auth)
):
    """
    取消电源操作
    
    **权限**: command:execute
    
    **功能**:
    - 取消已计划但未执行的电源操作
    - 仅对有延迟的操作有效
    
    **注意事项**:
    - 只能取消pending状态的操作
    - 已经执行的操作无法取消
    """
    manager = get_power_manager()
    
    with manager.engine.connect() as conn:
        # 检查操作是否存在
        result = conn.execute(
            text("SELECT action_id, status FROM power_actions WHERE action_id = :action_id"),
            {"action_id": action_id}
        )
        action = result.fetchone()
        
        if not action:
            raise HTTPException(status_code=404, detail=f"Power action not found: {action_id}")
        
        if action[1] != 'pending':
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel action with status: {action[1]}"
            )
        
        # 更新状态为cancelled
        conn.execute(
            text("""
                UPDATE power_actions 
                SET status = 'cancelled', updated_at = :updated_at
                WHERE action_id = :action_id
            """),
            {
                "action_id": action_id,
                "updated_at": datetime.now()
            }
        )
        conn.commit()
    
    return {
        "action_id": action_id,
        "status": "cancelled",
        "message": "Power action cancelled successfully"
    }
