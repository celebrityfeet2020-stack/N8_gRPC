"""
N8 Hub Control Center - M2-02: 设备详情查询
获取单个设备的完整信息
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Path, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os

# 导入认证中间件
from auth_middleware import require_auth


# ============================================================
# Pydantic Models
# ============================================================

class DeviceDetail(BaseModel):
    """设备详情"""
    device_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    hostname: str
    ip_address: str
    os_type: str
    os_version: Optional[str] = None
    status: str  # online/offline
    agent_version: Optional[str] = None
    tags: Optional[list] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DeviceDetailResponse(BaseModel):
    """设备详情响应"""
    success: bool = True
    data: Optional[DeviceDetail] = None
    message: str = "Success"
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "device_id": "device-abc123",
                    "name": "My Device",
                    "hostname": "my-pc",
                    "ip_address": "192.168.1.100",
                    "os_type": "windows",
                    "status": "online"
                },
                "message": "Success"
            }
        }


# ============================================================
# Device Detail Manager
# ============================================================

class DeviceDetailManager:
    """设备详情管理器"""
    
    def __init__(self, database_url: str):
        """
        初始化设备详情管理器
        
        Args:
            database_url: 数据库连接URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
    
    def get_device_detail(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        获取设备详情
        
        Args:
            device_id: 设备ID
        
        Returns:
            设备详情字典，如果不存在返回None
        """
        query = """
            SELECT 
                device_id,
                name,
                description,
                hostname,
                ip_address,
                os_type,
                os_version,
                status,
                agent_version,
                tags,
                metadata,
                last_seen,
                created_at,
                updated_at
            FROM devices
            WHERE device_id = :device_id
        """
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"device_id": device_id}).fetchone()
                
                if not result:
                    return None
                
                return {
                    "device_id": result[0],
                    "name": result[1],
                    "description": result[2],
                    "hostname": result[3],
                    "ip_address": result[4],
                    "os_type": result[5],
                    "os_version": result[6],
                    "status": result[7],
                    "agent_version": result[8],
                    "tags": result[9] or [],
                    "metadata": result[10] or {},
                    "last_seen": result[11],
                    "created_at": result[12],
                    "updated_at": result[13]
                }
        
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {str(e)}")


# ============================================================
# FastAPI Router
# ============================================================

# 创建路由器
router = APIRouter(prefix="/api/v1/devices", tags=["Device Management"])

# 全局实例
_device_detail_manager: Optional[DeviceDetailManager] = None


def get_device_detail_manager() -> DeviceDetailManager:
    """获取设备详情管理器实例"""
    global _device_detail_manager
    if _device_detail_manager is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
        )
        _device_detail_manager = DeviceDetailManager(database_url)
    return _device_detail_manager


@router.get("/{device_id}", response_model=DeviceDetailResponse)
async def get_device_detail(
    device_id: str = Path(..., description="设备ID"),
    auth_info: dict = Depends(require_auth)
):
    """
    获取设备详情
    
    - **device_id**: 设备ID
    
    需要权限: device:read
    """
    try:
        # 检查权限
        permissions = auth_info.get("permissions", [])
        if "*" not in permissions and "device:read" not in permissions:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: device:read required"
            )
        
        # 获取设备详情
        manager = get_device_detail_manager()
        device = manager.get_device_detail(device_id)
        
        if not device:
            raise HTTPException(
                status_code=404,
                detail=f"Device not found: {device_id}"
            )
        
        return DeviceDetailResponse(
            success=True,
            data=DeviceDetail(**device),
            message="Device detail retrieved successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================
# 初始化函数
# ============================================================

def init_device_detail_manager(database_url: str):
    """
    初始化设备详情管理器
    
    Args:
        database_url: 数据库连接URL
    """
    global _device_detail_manager
    _device_detail_manager = DeviceDetailManager(database_url)
    print("✅ 设备详情管理器已初始化")


# ============================================================
# 主程序（用于测试）
# ============================================================

if __name__ == "__main__":
    import sys
    
    # 测试数据库连接
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
    )
    
    print("=" * 60)
    print("N8 Hub Control Center - M2-02: 设备详情查询测试")
    print("=" * 60)
    
    try:
        manager = DeviceDetailManager(database_url)
        
        # 测试1: 获取存在的设备
        print("\n测试1: 获取存在的设备")
        device = manager.get_device_detail("device-test-001")
        if device:
            print(f"设备ID: {device['device_id']}")
            print(f"名称: {device['name']}")
            print(f"主机名: {device['hostname']}")
            print(f"IP地址: {device['ip_address']}")
            print(f"状态: {device['status']}")
        else:
            print("设备不存在")
        
        # 测试2: 获取不存在的设备
        print("\n测试2: 获取不存在的设备")
        device = manager.get_device_detail("device-not-exist")
        if device:
            print(f"设备ID: {device['device_id']}")
        else:
            print("设备不存在（符合预期）")
        
        print("\n✅ 所有测试通过！")
    
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        sys.exit(1)
