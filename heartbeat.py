"""
N8枢纽控制中心 - 心跳检测模块
提供心跳上报、设备状态自动更新、离线检测功能
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from auth_middleware import require_auth


# ==================== 配置 ====================

# 心跳超时时间（秒）
HEARTBEAT_TIMEOUT = 300  # 5分钟

# 离线检测间隔（秒）
OFFLINE_CHECK_INTERVAL = 60  # 1分钟


# ==================== Pydantic模型 ====================

class HeartbeatRequest(BaseModel):
    """心跳请求"""
    metrics: Optional[Dict[str, Any]] = Field(None, description="设备指标（CPU、内存、磁盘等）")
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据")


class HeartbeatResponse(BaseModel):
    """心跳响应"""
    device_id: str
    status: str
    last_seen: datetime
    next_heartbeat: int


# ==================== 心跳管理器 ====================

class HeartbeatManager:
    """心跳管理器"""
    
    def __init__(self, database_url: str):
        """
        初始化心跳管理器
        
        Args:
            database_url: PostgreSQL数据库连接URL
        """
        self.database_url = database_url
        self.heartbeat_timeout = HEARTBEAT_TIMEOUT
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(self.database_url)
    
    def report_heartbeat(
        self,
        device_id: str,
        metrics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        上报心跳
        
        更新设备的last_seen时间和状态为online
        可选地更新设备指标和元数据
        
        Args:
            device_id: 设备ID
            metrics: 设备指标（CPU、内存、磁盘等）
            metadata: 额外元数据
            
        Returns:
            心跳响应信息
            
        Raises:
            ValueError: 设备不存在
            psycopg2.Error: 数据库操作失败
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 检查设备是否存在
                cur.execute(
                    "SELECT * FROM devices WHERE device_id = %s",
                    (device_id,)
                )
                device = cur.fetchone()
                
                if not device:
                    raise ValueError(f"Device {device_id} not found")
                
                # 更新设备状态和last_seen时间
                now = datetime.now()
                
                # 构建更新语句
                update_fields = ["status = 'online'", "last_seen = %s"]
                params = [now]
                
                # 如果提供了指标，合并到元数据中
                if metrics or metadata:
                    current_metadata = device.get('metadata') or {}
                    
                    if metrics:
                        current_metadata['metrics'] = metrics
                        current_metadata['metrics_updated_at'] = now.isoformat()
                    
                    if metadata:
                        current_metadata.update(metadata)
                    
                    update_fields.append("metadata = %s")
                    params.append(psycopg2.extras.Json(current_metadata))
                
                params.append(device_id)
                
                query = f"UPDATE devices SET {', '.join(update_fields)} WHERE device_id = %s RETURNING *"
                cur.execute(query, params)
                
                updated_device = cur.fetchone()
                conn.commit()
                
                # 记录心跳日志（可选）
                self._log_heartbeat(device_id, metrics, metadata)
                
                return {
                    "device_id": device_id,
                    "status": "online",
                    "last_seen": now,
                    "next_heartbeat": self.heartbeat_timeout
                }
        finally:
            conn.close()
    
    def _log_heartbeat(
        self,
        device_id: str,
        metrics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        记录心跳日志（可选功能）
        
        Args:
            device_id: 设备ID
            metrics: 设备指标
            metadata: 额外元数据
        """
        # 这里可以实现心跳日志记录
        # 为了避免数据库压力，可以：
        # 1. 只记录关键心跳（如状态变化）
        # 2. 使用时序数据库（如InfluxDB）
        # 3. 使用消息队列异步处理
        pass
    
    def check_offline_devices(self) -> List[str]:
        """
        检查离线设备
        
        将超过heartbeat_timeout时间未上报心跳的设备标记为offline
        
        Returns:
            离线设备ID列表
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 计算离线阈值时间
                offline_threshold = datetime.now() - timedelta(seconds=self.heartbeat_timeout)
                
                # 查找超时的在线设备
                cur.execute(
                    """
                    SELECT device_id FROM devices
                    WHERE status = 'online' AND last_seen < %s
                    """,
                    (offline_threshold,)
                )
                
                offline_devices = [row['device_id'] for row in cur.fetchall()]
                
                if offline_devices:
                    # 批量更新为离线状态
                    cur.execute(
                        """
                        UPDATE devices
                        SET status = 'offline'
                        WHERE device_id = ANY(%s)
                        """,
                        (offline_devices,)
                    )
                    conn.commit()
                
                return offline_devices
        finally:
            conn.close()
    
    def get_device_heartbeat_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        获取设备心跳状态
        
        Args:
            device_id: 设备ID
            
        Returns:
            设备心跳状态信息，如果设备不存在则返回None
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT device_id, device_name, status, last_seen, registered_at
                    FROM devices
                    WHERE device_id = %s
                    """,
                    (device_id,)
                )
                
                device = cur.fetchone()
                
                if not device:
                    return None
                
                # 计算离线时长
                now = datetime.now()
                last_seen = device['last_seen']
                offline_duration = (now - last_seen).total_seconds()
                
                # 判断是否超时
                is_timeout = offline_duration > self.heartbeat_timeout
                
                return {
                    "device_id": device['device_id'],
                    "device_name": device['device_name'],
                    "status": device['status'],
                    "last_seen": last_seen,
                    "offline_duration": offline_duration,
                    "is_timeout": is_timeout,
                    "heartbeat_timeout": self.heartbeat_timeout,
                    "registered_at": device['registered_at']
                }
        finally:
            conn.close()
    
    def get_heartbeat_statistics(self) -> Dict[str, Any]:
        """
        获取心跳统计信息
        
        Returns:
            心跳统计信息
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 统计在线/离线设备数量
                cur.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM devices
                    GROUP BY status
                    """
                )
                
                status_counts = {row['status']: row['count'] for row in cur.fetchall()}
                
                # 统计总设备数
                cur.execute("SELECT COUNT(*) as total FROM devices")
                total_count = cur.fetchone()['total']
                
                # 统计最近5分钟活跃设备
                recent_threshold = datetime.now() - timedelta(minutes=5)
                cur.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM devices
                    WHERE last_seen >= %s
                    """,
                    (recent_threshold,)
                )
                recent_active = cur.fetchone()['count']
                
                return {
                    "total_devices": total_count,
                    "online_devices": status_counts.get('online', 0),
                    "offline_devices": status_counts.get('offline', 0),
                    "recent_active_devices": recent_active,
                    "heartbeat_timeout": self.heartbeat_timeout,
                    "timestamp": datetime.now()
                }
        finally:
            conn.close()


# ==================== API路由 ====================

# 创建路由
router = APIRouter(prefix="/api/v1/devices", tags=["Heartbeat"])

# 全局心跳管理器实例
_heartbeat_manager: Optional[HeartbeatManager] = None


def init_heartbeat_manager(database_url: str):
    """初始化全局心跳管理器实例"""
    global _heartbeat_manager
    _heartbeat_manager = HeartbeatManager(database_url)


def get_heartbeat_manager() -> HeartbeatManager:
    """获取全局心跳管理器实例"""
    if _heartbeat_manager is None:
        raise RuntimeError("HeartbeatManager not initialized")
    return _heartbeat_manager


@router.post("/{device_id}/heartbeat", response_model=Dict[str, Any])
async def report_heartbeat(
    device_id: str,
    request: HeartbeatRequest,
    background_tasks: BackgroundTasks,
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    上报心跳（Agent定期调用）
    
    建议心跳间隔：60秒
    心跳超时：300秒（5分钟）
    """
    manager = get_heartbeat_manager()
    
    try:
        heartbeat_info = manager.report_heartbeat(
            device_id=device_id,
            metrics=request.metrics,
            metadata=request.metadata
        )
        
        # 在后台检查离线设备（异步）
        background_tasks.add_task(manager.check_offline_devices)
        
        return {
            "status": "success",
            "message": "Heartbeat reported successfully",
            "data": heartbeat_info
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to report heartbeat: {str(e)}"
        )


@router.get("/{device_id}/heartbeat", response_model=Dict[str, Any])
async def get_heartbeat_status(
    device_id: str,
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    获取设备心跳状态
    
    需要 device:read 权限
    """
    from auth_middleware import get_auth_middleware
    
    # 检查权限
    auth = get_auth_middleware()
    if not auth.check_permissions(auth_info, ["device:read"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: device:read"
        )
    
    manager = get_heartbeat_manager()
    
    heartbeat_status = manager.get_device_heartbeat_status(device_id)
    
    if not heartbeat_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )
    
    return {
        "status": "success",
        "data": heartbeat_status
    }


@router.get("/heartbeat/statistics", response_model=Dict[str, Any])
async def get_heartbeat_statistics(
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    获取心跳统计信息
    
    需要 device:read 权限
    """
    from auth_middleware import get_auth_middleware
    
    # 检查权限
    auth = get_auth_middleware()
    if not auth.check_permissions(auth_info, ["device:read"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: device:read"
        )
    
    manager = get_heartbeat_manager()
    
    statistics = manager.get_heartbeat_statistics()
    
    return {
        "status": "success",
        "data": statistics
    }


@router.post("/heartbeat/check-offline", response_model=Dict[str, Any])
async def trigger_offline_check(
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    手动触发离线检测（管理员功能）
    
    需要 admin:write 权限
    """
    from auth_middleware import get_auth_middleware
    
    # 检查权限
    auth = get_auth_middleware()
    if not auth.check_permissions(auth_info, ["admin:write"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: admin:write"
        )
    
    manager = get_heartbeat_manager()
    
    offline_devices = manager.check_offline_devices()
    
    return {
        "status": "success",
        "message": f"Offline check completed, {len(offline_devices)} devices marked as offline",
        "data": {
            "offline_devices": offline_devices,
            "count": len(offline_devices)
        }
    }
