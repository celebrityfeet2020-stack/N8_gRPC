"""
N8 Hub Control Center - M2-06: 设备健康检查
检查设备健康状态并生成健康报告
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Path, Query, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os

# 导入认证中间件
from auth_middleware import require_auth


# ============================================================
# Pydantic Models
# ============================================================

class HealthCheckResult(BaseModel):
    """健康检查结果"""
    device_id: str
    health_status: str  # healthy/warning/critical/unknown
    health_score: int  # 0-100
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    last_check: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "device-abc123",
                "health_status": "healthy",
                "health_score": 95,
                "issues": [],
                "recommendations": [],
                "last_check": "2024-12-12T10:00:00"
            }
        }


class DeviceHealthResponse(BaseModel):
    """设备健康响应"""
    success: bool = True
    data: Optional[HealthCheckResult] = None
    message: str = "Success"


class BatchHealthCheckResponse(BaseModel):
    """批量健康检查响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    message: str = "Success"


# ============================================================
# Device Health Manager
# ============================================================

class DeviceHealthManager:
    """设备健康管理器"""
    
    # 健康检查阈值
    CPU_WARNING_THRESHOLD = 80.0
    CPU_CRITICAL_THRESHOLD = 95.0
    MEMORY_WARNING_THRESHOLD = 85.0
    MEMORY_CRITICAL_THRESHOLD = 95.0
    DISK_WARNING_THRESHOLD = 85.0
    DISK_CRITICAL_THRESHOLD = 95.0
    OFFLINE_WARNING_MINUTES = 10
    OFFLINE_CRITICAL_MINUTES = 60
    
    def __init__(self, database_url: str):
        """
        初始化设备健康管理器
        
        Args:
            database_url: 数据库连接URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
    
    def check_device_health(self, device_id: str) -> Dict[str, Any]:
        """
        检查单个设备健康状态
        
        Args:
            device_id: 设备ID
        
        Returns:
            健康检查结果
        
        Raises:
            ValueError: 如果设备不存在
        """
        # 获取设备信息和最新心跳
        query = """
            SELECT 
                d.device_id,
                d.status,
                d.last_seen,
                h.cpu_usage,
                h.memory_usage,
                h.disk_usage,
                h.timestamp
            FROM devices d
            LEFT JOIN (
                SELECT DISTINCT ON (device_id)
                    device_id,
                    cpu_usage,
                    memory_usage,
                    disk_usage,
                    timestamp
                FROM heartbeats
                ORDER BY device_id, timestamp DESC
            ) h ON d.device_id = h.device_id
            WHERE d.device_id = :device_id
        """
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"device_id": device_id}).fetchone()
                
                if not result:
                    raise ValueError(f"Device not found: {device_id}")
                
                device_id = result[0]
                status = result[1]
                last_seen = result[2]
                cpu_usage = result[3]
                memory_usage = result[4]
                disk_usage = result[5]
                heartbeat_time = result[6]
                
                # 执行健康检查
                issues = []
                recommendations = []
                health_score = 100
                health_status = "healthy"
                
                # 检查设备状态
                if status == "offline":
                    issues.append("设备离线")
                    health_score -= 50
                    health_status = "critical"
                    recommendations.append("检查设备网络连接和Agent服务")
                elif last_seen:
                    minutes_since_seen = (datetime.now() - last_seen).total_seconds() / 60
                    if minutes_since_seen > self.OFFLINE_CRITICAL_MINUTES:
                        issues.append(f"设备超过{int(minutes_since_seen)}分钟未响应")
                        health_score -= 40
                        health_status = "critical"
                        recommendations.append("检查设备是否正常运行")
                    elif minutes_since_seen > self.OFFLINE_WARNING_MINUTES:
                        issues.append(f"设备超过{int(minutes_since_seen)}分钟未响应")
                        health_score -= 20
                        if health_status == "healthy":
                            health_status = "warning"
                        recommendations.append("监控设备网络状况")
                
                # 检查CPU使用率
                if cpu_usage is not None:
                    if cpu_usage >= self.CPU_CRITICAL_THRESHOLD:
                        issues.append(f"CPU使用率过高: {cpu_usage}%")
                        health_score -= 20
                        health_status = "critical"
                        recommendations.append("检查CPU密集型进程")
                    elif cpu_usage >= self.CPU_WARNING_THRESHOLD:
                        issues.append(f"CPU使用率较高: {cpu_usage}%")
                        health_score -= 10
                        if health_status == "healthy":
                            health_status = "warning"
                        recommendations.append("监控CPU使用情况")
                
                # 检查内存使用率
                if memory_usage is not None:
                    if memory_usage >= self.MEMORY_CRITICAL_THRESHOLD:
                        issues.append(f"内存使用率过高: {memory_usage}%")
                        health_score -= 20
                        health_status = "critical"
                        recommendations.append("检查内存泄漏或关闭不必要的程序")
                    elif memory_usage >= self.MEMORY_WARNING_THRESHOLD:
                        issues.append(f"内存使用率较高: {memory_usage}%")
                        health_score -= 10
                        if health_status == "healthy":
                            health_status = "warning"
                        recommendations.append("监控内存使用情况")
                
                # 检查磁盘使用率
                if disk_usage is not None:
                    if disk_usage >= self.DISK_CRITICAL_THRESHOLD:
                        issues.append(f"磁盘使用率过高: {disk_usage}%")
                        health_score -= 20
                        health_status = "critical"
                        recommendations.append("清理磁盘空间或扩容")
                    elif disk_usage >= self.DISK_WARNING_THRESHOLD:
                        issues.append(f"磁盘使用率较高: {disk_usage}%")
                        health_score -= 10
                        if health_status == "healthy":
                            health_status = "warning"
                        recommendations.append("监控磁盘使用情况")
                
                # 确保健康分数不低于0
                health_score = max(0, health_score)
                
                # 如果没有心跳数据
                if cpu_usage is None and memory_usage is None and disk_usage is None:
                    if status == "online":
                        health_status = "unknown"
                        issues.append("缺少性能指标数据")
                        recommendations.append("等待设备上报心跳数据")
                
                return {
                    "device_id": device_id,
                    "health_status": health_status,
                    "health_score": health_score,
                    "issues": issues,
                    "recommendations": recommendations,
                    "last_check": datetime.now()
                }
        
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {str(e)}")
    
    def check_all_devices_health(self) -> Dict[str, Any]:
        """
        检查所有设备健康状态
        
        Returns:
            所有设备的健康检查结果汇总
        """
        # 获取所有设备ID
        query = "SELECT device_id FROM devices"
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                device_ids = [row[0] for row in result]
                
                # 检查每个设备
                results = []
                summary = {
                    "total": len(device_ids),
                    "healthy": 0,
                    "warning": 0,
                    "critical": 0,
                    "unknown": 0
                }
                
                for device_id in device_ids:
                    try:
                        health = self.check_device_health(device_id)
                        results.append(health)
                        
                        # 更新汇总
                        status = health["health_status"]
                        if status in summary:
                            summary[status] += 1
                    except Exception as e:
                        print(f"Error checking device {device_id}: {str(e)}")
                
                return {
                    "summary": summary,
                    "devices": results
                }
        
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {str(e)}")


# ============================================================
# FastAPI Router
# ============================================================

# 创建路由器
router = APIRouter(prefix="/api/v1/devices", tags=["Device Management"])

# 全局实例
_device_health_manager: Optional[DeviceHealthManager] = None


def get_device_health_manager() -> DeviceHealthManager:
    """获取设备健康管理器实例"""
    global _device_health_manager
    if _device_health_manager is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
        )
        _device_health_manager = DeviceHealthManager(database_url)
    return _device_health_manager


@router.get("/{device_id}/health", response_model=DeviceHealthResponse)
async def check_device_health(
    device_id: str = Path(..., description="设备ID"),
    auth_info: dict = Depends(require_auth)
):
    """
    检查单个设备健康状态
    
    - **device_id**: 设备ID
    
    返回设备健康状态、健康分数、问题列表和建议
    
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
        
        # 检查设备健康
        manager = get_device_health_manager()
        result = manager.check_device_health(device_id)
        
        return DeviceHealthResponse(
            success=True,
            data=HealthCheckResult(**result),
            message="Device health check completed"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/health/check-all", response_model=BatchHealthCheckResponse)
async def check_all_devices_health(
    auth_info: dict = Depends(require_auth)
):
    """
    检查所有设备健康状态
    
    返回所有设备的健康检查结果和汇总信息
    
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
        
        # 检查所有设备健康
        manager = get_device_health_manager()
        result = manager.check_all_devices_health()
        
        return BatchHealthCheckResponse(
            success=True,
            data=result,
            message="All devices health check completed"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================
# 初始化函数
# ============================================================

def init_device_health_manager(database_url: str):
    """
    初始化设备健康管理器
    
    Args:
        database_url: 数据库连接URL
    """
    global _device_health_manager
    _device_health_manager = DeviceHealthManager(database_url)
    print("✅ 设备健康管理器已初始化")


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
    print("N8 Hub Control Center - M2-06: 设备健康检查测试")
    print("=" * 60)
    
    try:
        manager = DeviceHealthManager(database_url)
        
        # 测试1: 检查单个设备健康
        print("\n测试1: 检查单个设备健康")
        result = manager.check_device_health("device-test-001")
        print(f"设备ID: {result['device_id']}")
        print(f"健康状态: {result['health_status']}")
        print(f"健康分数: {result['health_score']}")
        print(f"问题数量: {len(result['issues'])}")
        if result['issues']:
            print("问题列表:")
            for issue in result['issues']:
                print(f"  - {issue}")
        if result['recommendations']:
            print("建议:")
            for rec in result['recommendations']:
                print(f"  - {rec}")
        
        # 测试2: 检查所有设备健康
        print("\n测试2: 检查所有设备健康")
        result = manager.check_all_devices_health()
        summary = result['summary']
        print(f"总设备数: {summary['total']}")
        print(f"健康设备: {summary['healthy']}")
        print(f"警告设备: {summary['warning']}")
        print(f"严重设备: {summary['critical']}")
        print(f"未知状态: {summary['unknown']}")
        
        print("\n✅ 所有测试通过！")
    
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        sys.exit(1)
