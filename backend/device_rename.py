"""
N8 Hub Control Center - M2-03: 设备重命名
更新设备名称和描述
"""

from typing import Optional
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

class DeviceRenameRequest(BaseModel):
    """设备重命名请求"""
    name: Optional[str] = Field(None, max_length=255, description="设备名称")
    description: Optional[str] = Field(None, max_length=1000, description="设备描述")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Windows PC",
                "description": "主力开发机器"
            }
        }


class DeviceRenameResponse(BaseModel):
    """设备重命名响应"""
    success: bool = True
    data: dict = Field(default_factory=dict)
    message: str = "Success"
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "device_id": "device-abc123",
                    "name": "My Windows PC",
                    "description": "主力开发机器",
                    "updated_at": "2024-12-12T10:00:00"
                },
                "message": "Device renamed successfully"
            }
        }


# ============================================================
# Device Rename Manager
# ============================================================

class DeviceRenameManager:
    """设备重命名管理器"""
    
    def __init__(self, database_url: str):
        """
        初始化设备重命名管理器
        
        Args:
            database_url: 数据库连接URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
    
    def rename_device(
        self,
        device_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> dict:
        """
        重命名设备
        
        Args:
            device_id: 设备ID
            name: 新名称（可选）
            description: 新描述（可选）
        
        Returns:
            更新后的设备信息
        
        Raises:
            ValueError: 如果设备不存在或参数无效
        """
        # 至少要提供一个字段
        if name is None and description is None:
            raise ValueError("At least one of name or description must be provided")
        
        # 检查设备是否存在
        check_query = "SELECT device_id FROM devices WHERE device_id = :device_id"
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(check_query), {"device_id": device_id}).fetchone()
                
                if not result:
                    raise ValueError(f"Device not found: {device_id}")
                
                # 构建更新语句
                update_fields = []
                params = {"device_id": device_id, "updated_at": datetime.now()}
                
                if name is not None:
                    update_fields.append("name = :name")
                    params["name"] = name
                
                if description is not None:
                    update_fields.append("description = :description")
                    params["description"] = description
                
                update_fields.append("updated_at = :updated_at")
                
                update_query = f"""
                    UPDATE devices
                    SET {", ".join(update_fields)}
                    WHERE device_id = :device_id
                    RETURNING device_id, name, description, updated_at
                """
                
                # 执行更新
                result = conn.execute(text(update_query), params)
                conn.commit()
                
                row = result.fetchone()
                
                return {
                    "device_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "updated_at": row[3]
                }
        
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {str(e)}")


# ============================================================
# FastAPI Router
# ============================================================

# 创建路由器
router = APIRouter(prefix="/api/v1/devices", tags=["Device Management"])

# 全局实例
_device_rename_manager: Optional[DeviceRenameManager] = None


def get_device_rename_manager() -> DeviceRenameManager:
    """获取设备重命名管理器实例"""
    global _device_rename_manager
    if _device_rename_manager is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
        )
        _device_rename_manager = DeviceRenameManager(database_url)
    return _device_rename_manager


@router.put("/{device_id}/rename", response_model=DeviceRenameResponse)
async def rename_device(
    device_id: str = Path(..., description="设备ID"),
    request: DeviceRenameRequest = ...,
    auth_info: dict = Depends(require_auth)
):
    """
    重命名设备
    
    - **device_id**: 设备ID
    - **name**: 新名称（可选）
    - **description**: 新描述（可选）
    
    至少需要提供name或description之一。
    
    需要权限: device:write
    """
    try:
        # 检查权限
        permissions = auth_info.get("permissions", [])
        if "*" not in permissions and "device:write" not in permissions:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: device:write required"
            )
        
        # 重命名设备
        manager = get_device_rename_manager()
        result = manager.rename_device(
            device_id=device_id,
            name=request.name,
            description=request.description
        )
        
        return DeviceRenameResponse(
            success=True,
            data=result,
            message="Device renamed successfully"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================
# 初始化函数
# ============================================================

def init_device_rename_manager(database_url: str):
    """
    初始化设备重命名管理器
    
    Args:
        database_url: 数据库连接URL
    """
    global _device_rename_manager
    _device_rename_manager = DeviceRenameManager(database_url)
    print("✅ 设备重命名管理器已初始化")


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
    print("N8 Hub Control Center - M2-03: 设备重命名测试")
    print("=" * 60)
    
    try:
        manager = DeviceRenameManager(database_url)
        
        # 测试1: 重命名设备
        print("\n测试1: 重命名设备")
        result = manager.rename_device(
            device_id="device-test-001",
            name="测试设备（已重命名）",
            description="这是一个测试设备"
        )
        print(f"设备ID: {result['device_id']}")
        print(f"新名称: {result['name']}")
        print(f"新描述: {result['description']}")
        print(f"更新时间: {result['updated_at']}")
        
        # 测试2: 只更新名称
        print("\n测试2: 只更新名称")
        result = manager.rename_device(
            device_id="device-test-001",
            name="测试设备（再次重命名）"
        )
        print(f"新名称: {result['name']}")
        
        # 测试3: 尝试重命名不存在的设备
        print("\n测试3: 尝试重命名不存在的设备")
        try:
            result = manager.rename_device(
                device_id="device-not-exist",
                name="不存在的设备"
            )
        except ValueError as e:
            print(f"错误（符合预期）: {str(e)}")
        
        print("\n✅ 所有测试通过！")
    
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        sys.exit(1)
