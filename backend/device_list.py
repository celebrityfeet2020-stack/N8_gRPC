"""
N8 Hub Control Center - M2-01: 设备列表查询
支持分页、过滤、排序
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os

# 导入认证中间件
from auth_middleware import require_auth


# ============================================================
# Pydantic Models
# ============================================================

class DeviceListItem(BaseModel):
    """设备列表项"""
    device_id: str
    name: Optional[str] = None
    hostname: str
    ip_address: str
    os_type: str
    os_version: Optional[str] = None
    status: str  # online/offline
    agent_version: Optional[str] = None
    last_seen: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    """设备列表响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    message: str = "Success"
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "devices": [],
                    "total": 0,
                    "page": 1,
                    "page_size": 20
                },
                "message": "Success"
            }
        }


# ============================================================
# Device List Manager
# ============================================================

class DeviceListManager:
    """设备列表管理器"""
    
    def __init__(self, database_url: str):
        """
        初始化设备列表管理器
        
        Args:
            database_url: 数据库连接URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
    
    def get_devices(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        os_type: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        获取设备列表
        
        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            status: 状态过滤（online/offline）
            os_type: 操作系统类型过滤
            sort_by: 排序字段
            sort_order: 排序方向（asc/desc）
        
        Returns:
            包含设备列表和分页信息的字典
        """
        # 参数验证
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")
        if sort_order not in ["asc", "desc"]:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        
        # 允许的排序字段
        allowed_sort_fields = [
            "device_id", "name", "hostname", "ip_address",
            "os_type", "status", "last_seen", "created_at"
        ]
        if sort_by not in allowed_sort_fields:
            raise ValueError(f"sort_by must be one of: {', '.join(allowed_sort_fields)}")
        
        # 构建WHERE子句
        where_clauses = []
        params = {}
        
        if status:
            where_clauses.append("status = :status")
            params["status"] = status
        
        if os_type:
            where_clauses.append("os_type = :os_type")
            params["os_type"] = os_type
        
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
        
        # 计算偏移量
        offset = (page - 1) * page_size
        
        # 构建查询
        count_query = f"""
            SELECT COUNT(*) as total
            FROM devices
            {where_sql}
        """
        
        list_query = f"""
            SELECT 
                device_id,
                name,
                hostname,
                ip_address,
                os_type,
                os_version,
                status,
                agent_version,
                last_seen,
                created_at
            FROM devices
            {where_sql}
            ORDER BY {sort_by} {sort_order.upper()}
            LIMIT :limit OFFSET :offset
        """
        
        params["limit"] = page_size
        params["offset"] = offset
        
        try:
            with self.engine.connect() as conn:
                # 获取总数
                count_result = conn.execute(text(count_query), params).fetchone()
                total = count_result[0] if count_result else 0
                
                # 获取设备列表
                result = conn.execute(text(list_query), params)
                devices = []
                
                for row in result:
                    device = {
                        "device_id": row[0],
                        "name": row[1],
                        "hostname": row[2],
                        "ip_address": row[3],
                        "os_type": row[4],
                        "os_version": row[5],
                        "status": row[6],
                        "agent_version": row[7],
                        "last_seen": row[8],
                        "created_at": row[9]
                    }
                    devices.append(device)
                
                return {
                    "devices": devices,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
                }
        
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {str(e)}")


# ============================================================
# FastAPI Router
# ============================================================

# 创建路由器
router = APIRouter(prefix="/api/v1/devices", tags=["Device Management"])

# 全局实例
_device_list_manager: Optional[DeviceListManager] = None


def get_device_list_manager() -> DeviceListManager:
    """获取设备列表管理器实例"""
    global _device_list_manager
    if _device_list_manager is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
        )
        _device_list_manager = DeviceListManager(database_url)
    return _device_list_manager


@router.get("/list", response_model=DeviceListResponse)
async def list_devices(
    page: int = Query(1, ge=1, description="页码（从1开始）"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量（1-100）"),
    status: Optional[str] = Query(None, description="状态过滤（online/offline）"),
    os_type: Optional[str] = Query(None, description="操作系统类型过滤"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向（asc/desc）"),
    auth_info: dict = Depends(require_auth)
):
    """
    获取设备列表
    
    - **page**: 页码（从1开始）
    - **page_size**: 每页数量（1-100）
    - **status**: 状态过滤（online/offline）
    - **os_type**: 操作系统类型过滤（windows/linux/darwin）
    - **sort_by**: 排序字段（device_id/name/hostname/ip_address/os_type/status/last_seen/created_at）
    - **sort_order**: 排序方向（asc/desc）
    
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
        
        # 获取设备列表
        manager = get_device_list_manager()
        result = manager.get_devices(
            page=page,
            page_size=page_size,
            status=status,
            os_type=os_type,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return DeviceListResponse(
            success=True,
            data=result,
            message="Device list retrieved successfully"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================
# 初始化函数
# ============================================================

def init_device_list_manager(database_url: str):
    """
    初始化设备列表管理器
    
    Args:
        database_url: 数据库连接URL
    """
    global _device_list_manager
    _device_list_manager = DeviceListManager(database_url)
    print("✅ 设备列表管理器已初始化")


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
    print("N8 Hub Control Center - M2-01: 设备列表查询测试")
    print("=" * 60)
    
    try:
        manager = DeviceListManager(database_url)
        
        # 测试1: 获取所有设备（第1页）
        print("\n测试1: 获取所有设备（第1页，每页20条）")
        result = manager.get_devices(page=1, page_size=20)
        print(f"总数: {result['total']}")
        print(f"当前页: {result['page']}/{result['total_pages']}")
        print(f"设备数量: {len(result['devices'])}")
        for device in result['devices']:
            print(f"  - {device['device_id']}: {device['name']} ({device['status']})")
        
        # 测试2: 过滤在线设备
        print("\n测试2: 过滤在线设备")
        result = manager.get_devices(page=1, page_size=20, status="online")
        print(f"在线设备数量: {result['total']}")
        
        # 测试3: 按名称排序
        print("\n测试3: 按名称升序排序")
        result = manager.get_devices(page=1, page_size=20, sort_by="name", sort_order="asc")
        print(f"设备列表:")
        for device in result['devices']:
            print(f"  - {device['name'] or '(unnamed)'}: {device['device_id']}")
        
        print("\n✅ 所有测试通过！")
    
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        sys.exit(1)
