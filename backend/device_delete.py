"""
N8 Hub Control Center - M2-04: 设备删除
删除设备及其相关数据
"""

from typing import Optional
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

class DeviceDeleteResponse(BaseModel):
    """设备删除响应"""
    success: bool = True
    data: dict = Field(default_factory=dict)
    message: str = "Success"
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "device_id": "device-abc123",
                    "deleted": True
                },
                "message": "Device deleted successfully"
            }
        }


# ============================================================
# Device Delete Manager
# ============================================================

class DeviceDeleteManager:
    """设备删除管理器"""
    
    def __init__(self, database_url: str):
        """
        初始化设备删除管理器
        
        Args:
            database_url: 数据库连接URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
    
    def delete_device(self, device_id: str) -> dict:
        """
        删除设备
        
        删除设备及其相关的心跳记录。
        
        Args:
            device_id: 设备ID
        
        Returns:
            删除结果
        
        Raises:
            ValueError: 如果设备不存在
        """
        # 检查设备是否存在
        check_query = "SELECT device_id FROM devices WHERE device_id = :device_id"
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(check_query), {"device_id": device_id}).fetchone()
                
                if not result:
                    raise ValueError(f"Device not found: {device_id}")
                
                # 删除心跳记录（级联删除）
                delete_heartbeats_query = """
                    DELETE FROM heartbeats
                    WHERE device_id = :device_id
                """
                conn.execute(text(delete_heartbeats_query), {"device_id": device_id})
                
                # 删除设备
                delete_device_query = """
                    DELETE FROM devices
                    WHERE device_id = :device_id
                """
                conn.execute(text(delete_device_query), {"device_id": device_id})
                
                conn.commit()
                
                return {
                    "device_id": device_id,
                    "deleted": True
                }
        
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {str(e)}")


# ============================================================
# FastAPI Router
# ============================================================

# 创建路由器
router = APIRouter(prefix="/api/v1/devices", tags=["Device Management"])

# 全局实例
_device_delete_manager: Optional[DeviceDeleteManager] = None


def get_device_delete_manager() -> DeviceDeleteManager:
    """获取设备删除管理器实例"""
    global _device_delete_manager
    if _device_delete_manager is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
        )
        _device_delete_manager = DeviceDeleteManager(database_url)
    return _device_delete_manager


@router.delete("/{device_id}", response_model=DeviceDeleteResponse)
async def delete_device(
    device_id: str = Path(..., description="设备ID"),
    auth_info: dict = Depends(require_auth)
):
    """
    删除设备
    
    - **device_id**: 设备ID
    
    删除设备及其相关的心跳记录。此操作不可逆！
    
    需要权限: device:delete
    """
    try:
        # 检查权限
        permissions = auth_info.get("permissions", [])
        if "*" not in permissions and "device:delete" not in permissions:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: device:delete required"
            )
        
        # 删除设备
        manager = get_device_delete_manager()
        result = manager.delete_device(device_id)
        
        return DeviceDeleteResponse(
            success=True,
            data=result,
            message="Device deleted successfully"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================
# 初始化函数
# ============================================================

def init_device_delete_manager(database_url: str):
    """
    初始化设备删除管理器
    
    Args:
        database_url: 数据库连接URL
    """
    global _device_delete_manager
    _device_delete_manager = DeviceDeleteManager(database_url)
    print("✅ 设备删除管理器已初始化")


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
    print("N8 Hub Control Center - M2-04: 设备删除测试")
    print("=" * 60)
    
    try:
        manager = DeviceDeleteManager(database_url)
        
        # 测试1: 删除存在的设备
        print("\n测试1: 删除存在的设备")
        result = manager.delete_device("device-test-001")
        print(f"设备ID: {result['device_id']}")
        print(f"已删除: {result['deleted']}")
        
        # 测试2: 尝试删除不存在的设备
        print("\n测试2: 尝试删除不存在的设备")
        try:
            result = manager.delete_device("device-not-exist")
        except ValueError as e:
            print(f"错误（符合预期）: {str(e)}")
        
        print("\n✅ 所有测试通过！")
    
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        sys.exit(1)
