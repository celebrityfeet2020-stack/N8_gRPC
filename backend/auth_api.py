"""
N8枢纽控制中心 - 认证管理API
提供API Key的CRUD接口
"""

import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
from datetime import datetime

from api_key_manager import APIKeyManager
from auth_middleware import require_api_key

# 创建路由器 - 修改前缀以匹配前端请求
router = APIRouter(
    prefix="/api/v1/api-keys",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

# 数据库连接URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
)

# 全局API Key管理器实例
_api_key_manager = None

def get_api_key_manager():
    """获取API Key管理器单例"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager(DATABASE_URL)
    return _api_key_manager

# --- 请求/响应模型 ---

class APIKeyCreateRequest(BaseModel):
    """创建API Key请求"""
    api_name: str = Field(..., description="API名称")
    api_type: Optional[str] = Field("general", description="API类型 (已废弃，默认为general)")
    permissions: Optional[List[str]] = Field(None, description="权限列表")
    expires_days: Optional[int] = Field(None, description="过期天数")

class APIKeyUpdateRequest(BaseModel):
    """更新API Key请求"""
    api_name: Optional[str] = Field(None, description="新的API名称")
    permissions: Optional[List[str]] = Field(None, description="新的权限列表")
    is_active: Optional[bool] = Field(None, description="是否激活")

class APIKeyResponse(BaseModel):
    """API Key响应"""
    id: int
    api_key: str
    api_name: str
    api_type: str
    permissions: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime

# --- 路由定义 ---

@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    api_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    manager: APIKeyManager = Depends(get_api_key_manager),
    auth_info: Dict[str, Any] = Depends(require_api_key)
):
    """
    列出所有API Key
    """
    # 移除类型检查，所有有效Key均可访问
    keys = manager.list_api_keys(api_type, is_active, limit, offset)
    return keys

@router.post("", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    manager: APIKeyManager = Depends(get_api_key_manager),
    auth_info: Dict[str, Any] = Depends(require_api_key)
):
    """
    创建新的API Key
    """
    # 移除类型检查
    try:
        result = manager.create_api_key(
            api_name=request.api_name,
            api_type="general", # 强制使用 general
            expires_days=request.expires_days,
            created_by=auth_info.get("api_name", "unknown")
        )
        return result
    except ValueError as e:
        # 捕获名称重复等错误
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{key_id}", response_model=Dict[str, str])
async def update_api_key(
    key_id: int,
    request: APIKeyUpdateRequest,
    manager: APIKeyManager = Depends(get_api_key_manager),
    auth_info: Dict[str, Any] = Depends(require_api_key)
):
    """
    更新API Key
    """
    # 移除类型检查
    success = manager.update_api_key(
        api_key_id=key_id,
        api_name=request.api_name,
        permissions=request.permissions,
        is_active=request.is_active
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    return {"status": "success", "message": "API Key updated"}

@router.delete("/{key_id}", response_model=Dict[str, str])
async def delete_api_key(
    key_id: int,
    manager: APIKeyManager = Depends(get_api_key_manager),
    auth_info: Dict[str, Any] = Depends(require_api_key)
):
    """
    删除API Key
    """
    # 移除类型检查
    
    # 防止删除自己
    current_key_id = auth_info.get("id")
    if current_key_id == key_id:
        raise HTTPException(status_code=400, detail="Cannot delete current API Key")
        
    success = manager.delete_api_key(key_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    return {"status": "success", "message": "API Key deleted"}
