"""
N8枢纽控制中心 - M3-02 屏幕截图模块
支持多显示器，支持Session 0（Windows服务会话）
"""

import os
import uuid
import base64
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

class ScreenshotRequest(BaseModel):
    """屏幕截图请求"""
    device_id: str = Field(..., description="设备ID")
    monitor_index: Optional[int] = Field(None, description="显示器索引（None表示所有显示器）")
    quality: Optional[int] = Field(85, description="图片质量（1-100），默认85")
    format: Optional[str] = Field("png", description="图片格式：png/jpg/bmp")
    include_cursor: Optional[bool] = Field(True, description="是否包含鼠标指针")


class ScreenshotResponse(BaseModel):
    """屏幕截图响应"""
    screenshot_id: str = Field(..., description="截图ID")
    device_id: str = Field(..., description="设备ID")
    monitor_count: int = Field(..., description="显示器数量")
    screenshots: List[dict] = Field(..., description="截图列表")
    created_at: str = Field(..., description="创建时间")


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/api/v1/commands", tags=["M3-CommandExecution"])


# ============================================================
# Database Manager
# ============================================================

class ScreenshotManager:
    """屏幕截图管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = sqlalchemy.create_engine(database_url)
    
    async def take_screenshot(
        self,
        device_id: str,
        monitor_index: Optional[int] = None,
        quality: int = 85,
        format: str = "png",
        include_cursor: bool = True
    ) -> dict:
        """
        执行屏幕截图
        
        Args:
            device_id: 设备ID
            monitor_index: 显示器索引（None表示所有显示器）
            quality: 图片质量（1-100）
            format: 图片格式
            include_cursor: 是否包含鼠标指针
        
        Returns:
            截图结果字典
        """
        # 生成截图ID
        screenshot_id = f"screenshot-{uuid.uuid4().hex[:16]}"
        
        # 检查设备是否存在
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
        
        os_type = device[2]
        
        # 注意：这里是服务端代码，实际截图需要Agent端执行
        # 这里只是创建截图任务记录，Agent会轮询并执行
        
        # 创建截图任务
        created_at = datetime.now()
        
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO screenshot_tasks 
                    (screenshot_id, device_id, monitor_index, quality, format, 
                     include_cursor, status, created_at)
                    VALUES (:screenshot_id, :device_id, :monitor_index, :quality, :format,
                            :include_cursor, :status, :created_at)
                """),
                {
                    "screenshot_id": screenshot_id,
                    "device_id": device_id,
                    "monitor_index": monitor_index,
                    "quality": quality,
                    "format": format,
                    "include_cursor": include_cursor,
                    "status": "pending",
                    "created_at": created_at
                }
            )
            conn.commit()
        
        return {
            "screenshot_id": screenshot_id,
            "device_id": device_id,
            "status": "pending",
            "message": "Screenshot task created. Agent will execute it.",
            "created_at": created_at.isoformat()
        }
    
    async def get_screenshot(self, screenshot_id: str) -> Optional[dict]:
        """
        获取截图结果
        
        Args:
            screenshot_id: 截图ID
        
        Returns:
            截图结果字典，如果不存在则返回None
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT screenshot_id, device_id, monitor_count, status, 
                           error_message, created_at, completed_at
                    FROM screenshot_tasks
                    WHERE screenshot_id = :screenshot_id
                """),
                {"screenshot_id": screenshot_id}
            )
            row = result.fetchone()
            
            if not row:
                return None
            
            # 获取截图文件列表
            result2 = conn.execute(
                text("""
                    SELECT monitor_index, width, height, file_path, file_size
                    FROM screenshot_files
                    WHERE screenshot_id = :screenshot_id
                    ORDER BY monitor_index
                """),
                {"screenshot_id": screenshot_id}
            )
            
            screenshots = []
            for file_row in result2:
                screenshots.append({
                    "monitor_index": file_row[0],
                    "width": file_row[1],
                    "height": file_row[2],
                    "file_path": file_row[3],
                    "file_size": file_row[4]
                })
            
            return {
                "screenshot_id": row[0],
                "device_id": row[1],
                "monitor_count": row[2] or 0,
                "status": row[3],
                "error_message": row[4],
                "screenshots": screenshots,
                "created_at": row[5].isoformat() if row[5] else None,
                "completed_at": row[6].isoformat() if row[6] else None
            }


# 全局管理器实例
_screenshot_manager: Optional[ScreenshotManager] = None


def get_screenshot_manager() -> ScreenshotManager:
    """获取屏幕截图管理器实例"""
    if _screenshot_manager is None:
        raise RuntimeError("ScreenshotManager not initialized")
    return _screenshot_manager


def init_screenshot_manager(database_url: str):
    """初始化屏幕截图管理器"""
    global _screenshot_manager
    _screenshot_manager = ScreenshotManager(database_url)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/screenshot", response_model=dict)
async def take_screenshot(
    request: ScreenshotRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    执行屏幕截图
    
    **权限**: command:execute
    
    **功能**:
    - 支持多显示器截图
    - 支持Session 0（Windows服务会话）
    - 支持自定义图片质量和格式
    - 支持包含/排除鼠标指针
    
    **工作流程**:
    1. 创建截图任务
    2. Agent轮询并执行任务
    3. Agent上传截图文件
    4. 通过GET /api/v1/commands/screenshots/{screenshot_id}查询结果
    
    **注意事项**:
    - 设备必须在线
    - 截图文件会保存到服务器
    - 支持Windows、macOS、Linux
    - Windows下支持Session 0截图（需要特殊工具）
    """
    manager = get_screenshot_manager()
    
    result = await manager.take_screenshot(
        device_id=request.device_id,
        monitor_index=request.monitor_index,
        quality=request.quality or 85,
        format=request.format or "png",
        include_cursor=request.include_cursor if request.include_cursor is not None else True
    )
    
    return result


@router.get("/screenshots/{screenshot_id}", response_model=dict)
async def get_screenshot(
    screenshot_id: str,
    auth_info: dict = Depends(require_auth)
):
    """
    获取截图结果
    
    **权限**: command:execute
    
    **功能**:
    - 查询截图任务状态
    - 获取截图文件信息
    - 下载截图文件
    
    **状态说明**:
    - pending: 等待执行
    - running: 执行中
    - completed: 完成
    - failed: 失败
    """
    manager = get_screenshot_manager()
    
    result = await manager.get_screenshot(screenshot_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Screenshot not found: {screenshot_id}")
    
    return result
