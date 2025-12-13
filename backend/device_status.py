"""
N8 Hub Control Center - M2-05: 设备状态监控
实时监控设备状态和性能指标
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
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

class DeviceStatusItem(BaseModel):
    """设备状态项"""
    device_id: str
    name: Optional[str] = None
    hostname: str
    ip_address: str
    status: str  # online/offline
    last_seen: Optional[datetime] = None
    uptime_seconds: Optional[int] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    
    class Config:
        from_attributes = True


class DeviceStatusSummary(BaseModel):
    """设备状态汇总"""
    total_devices: int
    online_devices: int
    offline_devices: int
    online_percentage: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_devices": 100,
                "online_devices": 85,
                "offline_devices": 15,
                "online_percentage": 85.0
            }
        }


class DeviceStatusResponse(BaseModel):
    """设备状态响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    message: str = "Success"
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "summary": {},
                    "devices": []
                },
                "message": "Success"
            }
        }


# ============================================================
# Device Status Manager
# ============================================================

class DeviceStatusManager:
    """设备状态管理器"""
    
    def __init__(self, database_url: str):
        """
        初始化设备状态管理器
        
        Args:
            database_url: 数据库连接URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
    
    def get_device_status_summary(self) -> Dict[str, Any]:
        """
        获取设备状态汇总
        
        Returns:
            设备状态汇总信息
        """
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) as online,
                SUM(CASE WHEN status = 'offline' THEN 1 ELSE 0 END) as offline
            FROM devices
        """
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query)).fetchone()
                
                total = result[0] or 0
                online = result[1] or 0
                offline = result[2] or 0
                
                online_percentage = (online / total * 100) if total > 0 else 0.0
                
                return {
                    "total_devices": total,
                    "online_devices": online,
                    "offline_devices": offline,
                    "online_percentage": round(online_percentage, 2)
                }
        
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {str(e)}")
    
    def get_device_status_list(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取设备状态列表
        
        Args:
            status: 状态过滤（online/offline）
            limit: 返回数量限制
        
        Returns:
            设备状态列表
        """
        # 构建WHERE子句
        where_clause = ""
        params = {"limit": limit}
        
        if status:
            where_clause = "WHERE d.status = :status"
            params["status"] = status
        
        query = f"""
            SELECT 
                d.device_id,
                d.name,
                d.hostname,
                d.ip_address,
                d.status,
                d.last_seen,
                h.uptime_seconds,
                h.cpu_usage,
                h.memory_usage,
                h.disk_usage
            FROM devices d
            LEFT JOIN (
                SELECT DISTINCT ON (device_id)
                    device_id,
                    uptime_seconds,
                    cpu_usage,
                    memory_usage,
                    disk_usage
                FROM heartbeats
                ORDER BY device_id, timestamp DESC
            ) h ON d.device_id = h.device_id
            {where_clause}
            ORDER BY d.last_seen DESC NULLS LAST
            LIMIT :limit
        """
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                devices = []
                
                for row in result:
                    device = {
                        "device_id": row[0],
                        "name": row[1],
                        "hostname": row[2],
                        "ip_address": row[3],
                        "status": row[4],
                        "last_seen": row[5],
                        "uptime_seconds": row[6],
                        "cpu_usage": row[7],
                        "memory_usage": row[8],
                        "disk_usage": row[9]
                    }
                    devices.append(device)
                
                return devices
        
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {str(e)}")


# ============================================================
# FastAPI Router
# ============================================================

# 创建路由器
router = APIRouter(prefix="/api/v1/devices", tags=["Device Management"])

# 全局实例
_device_status_manager: Optional[DeviceStatusManager] = None


def get_device_status_manager() -> DeviceStatusManager:
    """获取设备状态管理器实例"""
    global _device_status_manager
    if _device_status_manager is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
        )
        _device_status_manager = DeviceStatusManager(database_url)
    return _device_status_manager


@router.get("/status", response_model=DeviceStatusResponse)
async def get_device_status(
    status: Optional[str] = Query(None, description="状态过滤（online/offline）"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制（1-1000）"),
    auth_info: dict = Depends(require_auth)
):
    """
    获取设备状态监控信息
    
    - **status**: 状态过滤（online/offline）
    - **limit**: 返回数量限制（1-1000）
    
    返回设备状态汇总和设备列表（包含性能指标）
    
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
        
        # 获取设备状态
        manager = get_device_status_manager()
        summary = manager.get_device_status_summary()
        devices = manager.get_device_status_list(status=status, limit=limit)
        
        return DeviceStatusResponse(
            success=True,
            data={
                "summary": summary,
                "devices": devices
            },
            message="Device status retrieved successfully"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================
# 初始化函数
# ============================================================

def init_device_status_manager(database_url: str):
    """
    初始化设备状态管理器
    
    Args:
        database_url: 数据库连接URL
    """
    global _device_status_manager
    _device_status_manager = DeviceStatusManager(database_url)
    print("✅ 设备状态管理器已初始化")


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
    print("N8 Hub Control Center - M2-05: 设备状态监控测试")
    print("=" * 60)
    
    try:
        manager = DeviceStatusManager(database_url)
        
        # 测试1: 获取设备状态汇总
        print("\n测试1: 获取设备状态汇总")
        summary = manager.get_device_status_summary()
        print(f"总设备数: {summary['total_devices']}")
        print(f"在线设备: {summary['online_devices']}")
        print(f"离线设备: {summary['offline_devices']}")
        print(f"在线率: {summary['online_percentage']}%")
        
        # 测试2: 获取所有设备状态
        print("\n测试2: 获取所有设备状态（前10个）")
        devices = manager.get_device_status_list(limit=10)
        print(f"返回设备数: {len(devices)}")
        for device in devices:
            print(f"  - {device['device_id']}: {device['status']}")
            if device['cpu_usage'] is not None:
                print(f"    CPU: {device['cpu_usage']}%, 内存: {device['memory_usage']}%")
        
        # 测试3: 只获取在线设备
        print("\n测试3: 只获取在线设备")
        devices = manager.get_device_status_list(status="online", limit=10)
        print(f"在线设备数: {len(devices)}")
        
        print("\n✅ 所有测试通过！")
    
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        sys.exit(1)
