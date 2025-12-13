"""
N8枢纽控制中心 - M3-03 鼠标键盘控制模块
支持鼠标移动、点击、键盘输入
"""

import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import sqlalchemy
from sqlalchemy import text

# 导入认证中间件
from auth_middleware import require_auth


# ============================================================
# Pydantic Models
# ============================================================

class MouseMoveRequest(BaseModel):
    """鼠标移动请求"""
    device_id: str = Field(..., description="设备ID")
    x: int = Field(..., description="X坐标")
    y: int = Field(..., description="Y坐标")
    duration: Optional[float] = Field(0, description="移动持续时间（秒），0表示瞬间移动")


class MouseClickRequest(BaseModel):
    """鼠标点击请求"""
    device_id: str = Field(..., description="设备ID")
    x: Optional[int] = Field(None, description="X坐标（None表示当前位置）")
    y: Optional[int] = Field(None, description="Y坐标（None表示当前位置）")
    button: Optional[str] = Field("left", description="按钮：left/right/middle")
    clicks: Optional[int] = Field(1, description="点击次数")
    interval: Optional[float] = Field(0.1, description="点击间隔（秒）")


class KeyboardTypeRequest(BaseModel):
    """键盘输入请求"""
    device_id: str = Field(..., description="设备ID")
    text: str = Field(..., description="要输入的文本")
    interval: Optional[float] = Field(0.05, description="按键间隔（秒）")


class KeyboardPressRequest(BaseModel):
    """键盘按键请求"""
    device_id: str = Field(..., description="设备ID")
    keys: List[str] = Field(..., description="要按下的键（支持组合键，如['ctrl', 'c']）")


class InputControlResponse(BaseModel):
    """输入控制响应"""
    action_id: str = Field(..., description="操作ID")
    device_id: str = Field(..., description="设备ID")
    action_type: str = Field(..., description="操作类型")
    status: str = Field(..., description="状态：pending/completed/failed")
    created_at: str = Field(..., description="创建时间")


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/api/v1/commands", tags=["M3-CommandExecution"])


# ============================================================
# Database Manager
# ============================================================

class InputControlManager:
    """输入控制管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = sqlalchemy.create_engine(database_url)
    
    async def create_input_action(
        self,
        device_id: str,
        action_type: str,
        action_data: dict
    ) -> dict:
        """
        创建输入控制操作
        
        Args:
            device_id: 设备ID
            action_type: 操作类型
            action_data: 操作数据
        
        Returns:
            操作结果字典
        """
        # 生成操作ID
        action_id = f"input-{uuid.uuid4().hex[:16]}"
        
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
        
        # 创建输入控制任务
        created_at = datetime.now()
        
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO input_control_actions 
                    (action_id, device_id, action_type, action_data, status, created_at)
                    VALUES (:action_id, :device_id, :action_type, :action_data, :status, :created_at)
                """),
                {
                    "action_id": action_id,
                    "device_id": device_id,
                    "action_type": action_type,
                    "action_data": sqlalchemy.dialects.postgresql.JSONB(action_data),
                    "status": "pending",
                    "created_at": created_at
                }
            )
            conn.commit()
        
        return {
            "action_id": action_id,
            "device_id": device_id,
            "action_type": action_type,
            "status": "pending",
            "message": "Input control action created. Agent will execute it.",
            "created_at": created_at.isoformat()
        }


# 全局管理器实例
_input_control_manager: Optional[InputControlManager] = None


def get_input_control_manager() -> InputControlManager:
    """获取输入控制管理器实例"""
    if _input_control_manager is None:
        raise RuntimeError("InputControlManager not initialized")
    return _input_control_manager


def init_input_control_manager(database_url: str):
    """初始化输入控制管理器"""
    global _input_control_manager
    _input_control_manager = InputControlManager(database_url)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/mouse/move", response_model=InputControlResponse)
async def mouse_move(
    request: MouseMoveRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    移动鼠标
    
    **权限**: command:execute
    
    **功能**:
    - 移动鼠标到指定坐标
    - 支持平滑移动（设置duration）
    - 支持瞬间移动（duration=0）
    """
    manager = get_input_control_manager()
    
    result = await manager.create_input_action(
        device_id=request.device_id,
        action_type="mouse_move",
        action_data={
            "x": request.x,
            "y": request.y,
            "duration": request.duration or 0
        }
    )
    
    return InputControlResponse(**result)


@router.post("/mouse/click", response_model=InputControlResponse)
async def mouse_click(
    request: MouseClickRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    鼠标点击
    
    **权限**: command:execute
    
    **功能**:
    - 支持左键/右键/中键点击
    - 支持单击/双击/多次点击
    - 支持在指定坐标点击
    - 支持在当前位置点击
    """
    manager = get_input_control_manager()
    
    result = await manager.create_input_action(
        device_id=request.device_id,
        action_type="mouse_click",
        action_data={
            "x": request.x,
            "y": request.y,
            "button": request.button or "left",
            "clicks": request.clicks or 1,
            "interval": request.interval or 0.1
        }
    )
    
    return InputControlResponse(**result)


@router.post("/keyboard/type", response_model=InputControlResponse)
async def keyboard_type(
    request: KeyboardTypeRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    键盘输入文本
    
    **权限**: command:execute
    
    **功能**:
    - 模拟键盘输入文本
    - 支持自定义按键间隔
    - 支持特殊字符
    """
    manager = get_input_control_manager()
    
    result = await manager.create_input_action(
        device_id=request.device_id,
        action_type="keyboard_type",
        action_data={
            "text": request.text,
            "interval": request.interval or 0.05
        }
    )
    
    return InputControlResponse(**result)


@router.post("/keyboard/press", response_model=InputControlResponse)
async def keyboard_press(
    request: KeyboardPressRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    键盘按键
    
    **权限**: command:execute
    
    **功能**:
    - 模拟键盘按键
    - 支持组合键（如Ctrl+C）
    - 支持功能键（如F1-F12）
    - 支持特殊键（如Enter、Tab、Esc等）
    
    **按键示例**:
    - 单个按键: ["enter"]
    - 组合键: ["ctrl", "c"]
    - 多个组合键: ["ctrl", "shift", "esc"]
    """
    manager = get_input_control_manager()
    
    result = await manager.create_input_action(
        device_id=request.device_id,
        action_type="keyboard_press",
        action_data={
            "keys": request.keys
        }
    )
    
    return InputControlResponse(**result)
