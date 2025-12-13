"""
N8枢纽控制中心 - 设备注册模块
提供设备自动注册、设备ID生成、设备管理CRUD操作
"""

import hashlib
import socket
from datetime import datetime
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from auth_middleware import require_auth, get_auth_middleware


# ==================== Pydantic模型 ====================

class DeviceRegisterRequest(BaseModel):
    """设备注册请求"""
    hostname: str = Field(..., description="主机名")
    ip_address: str = Field(..., description="内网IP地址")
    os_type: str = Field(..., description="操作系统类型（linux/windows/macos）")
    os_version: str = Field(..., description="操作系统版本")
    agent_version: str = Field(..., description="Agent版本")
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据")


class DeviceUpdateRequest(BaseModel):
    """设备更新请求"""
    device_name: Optional[str] = Field(None, description="设备名称")
    description: Optional[str] = Field(None, description="设备描述")
    tags: Optional[List[str]] = Field(None, description="设备标签")
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据")


class DeviceResponse(BaseModel):
    """设备响应"""
    id: int
    device_id: str
    device_name: str
    hostname: str
    ip_address: str
    os_type: str
    os_version: str
    agent_version: str
    status: str
    last_seen_at: datetime
    registered_at: datetime
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


# ==================== 设备注册管理器 ====================

class DeviceRegistrationManager:
    """设备注册管理器"""
    
    def __init__(self, database_url: str):
        """
        初始化设备注册管理器
        
        Args:
            database_url: PostgreSQL数据库连接URL
        """
        self.database_url = database_url
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(self.database_url)
    
    def generate_device_id(self, ip_address: str, hostname: str) -> str:
        """
        生成唯一设备ID
        
        基于内网IP和主机名生成唯一ID，确保同一设备重复注册时使用相同ID
        
        Args:
            ip_address: 内网IP地址
            hostname: 主机名
            
        Returns:
            设备ID（格式：device-{hash}）
        """
        # 使用IP和主机名生成哈希
        data = f"{ip_address}:{hostname}".encode('utf-8')
        hash_value = hashlib.sha256(data).hexdigest()[:16]
        return f"device-{hash_value}"
    
    def register_device(
        self,
        hostname: str,
        ip_address: str,
        os_type: str,
        os_version: str,
        agent_version: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        注册设备（Agent调用）
        
        如果设备已存在（相同device_id），则更新信息和last_seen时间
        如果设备不存在，则创建新设备
        
        Args:
            hostname: 主机名
            ip_address: 内网IP地址
            os_type: 操作系统类型
            os_version: 操作系统版本
            agent_version: Agent版本
            metadata: 额外元数据
            
        Returns:
            设备信息
            
        Raises:
            psycopg2.Error: 数据库操作失败
        """
        # 生成设备ID
        device_id = self.generate_device_id(ip_address, hostname)
        
        # 检查设备是否已存在
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM devices WHERE device_id = %s",
                    (device_id,)
                )
                existing_device = cur.fetchone()
                
                if existing_device:
                    # 设备已存在，更新信息
                    cur.execute(
                        """
                        UPDATE devices
                        SET hostname = %s, ip_address = %s, os_type = %s, os_version = %s,
                            agent_version = %s, metadata = %s, last_seen_at = %s, status = 'online'
                        WHERE device_id = %s
                        RETURNING *
                        """,
                        (hostname, ip_address, os_type, os_version, agent_version,
                         psycopg2.extras.Json(metadata or {}), datetime.now(), device_id)
                    )
                else:
                    # 设备不存在，创建新设备
                    device_name = f"{hostname} ({ip_address})"
                    cur.execute(
                        """
                        INSERT INTO devices (device_id, device_name, hostname, ip_address, 
                                           os_type, os_version, agent_version, metadata, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'online')
                        RETURNING *
                        """,
                        (device_id, device_name, hostname, ip_address, os_type, 
                         os_version, agent_version, psycopg2.extras.Json(metadata or {}))
                    )
                
                device_info = cur.fetchone()
                conn.commit()
                
                return dict(device_info)
        finally:
            conn.close()
    
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        获取设备详情
        
        Args:
            device_id: 设备ID
            
        Returns:
            设备信息，如果不存在则返回None
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM devices WHERE device_id = %s",
                    (device_id,)
                )
                device_info = cur.fetchone()
                return dict(device_info) if device_info else None
        finally:
            conn.close()
    
    def list_devices(
        self,
        status: Optional[str] = None,
        os_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出设备
        
        Args:
            status: 过滤设备状态（online/offline）
            os_type: 过滤操作系统类型
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            设备列表
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 构建查询
                query = "SELECT * FROM devices WHERE 1=1"
                params = []
                
                if status:
                    query += " AND status = %s"
                    params.append(status)
                
                if os_type:
                    query += " AND os_type = %s"
                    params.append(os_type)
                
                query += " ORDER BY last_seen_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                devices = cur.fetchall()
                
                return [dict(device) for device in devices]
        finally:
            conn.close()
    
    def update_device(
        self,
        device_id: str,
        device_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        更新设备信息（Web后台调用）
        
        Args:
            device_id: 设备ID
            device_name: 设备名称
            description: 设备描述
            tags: 设备标签
            metadata: 额外元数据
            
        Returns:
            更新后的设备信息，如果设备不存在则返回None
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 构建更新语句
                updates = []
                params = []
                
                if device_name is not None:
                    updates.append("device_name = %s")
                    params.append(device_name)
                
                if description is not None:
                    updates.append("description = %s")
                    params.append(description)
                
                if tags is not None:
                    updates.append("tags = %s")
                    params.append(tags)
                
                if metadata is not None:
                    updates.append("metadata = %s")
                    params.append(psycopg2.extras.Json(metadata))
                
                if not updates:
                    # 没有更新内容，直接返回当前设备信息
                    return self.get_device(device_id)
                
                query = f"UPDATE devices SET {', '.join(updates)} WHERE device_id = %s RETURNING *"
                params.append(device_id)
                
                cur.execute(query, params)
                device_info = cur.fetchone()
                conn.commit()
                
                return dict(device_info) if device_info else None
        finally:
            conn.close()
    
    def delete_device(self, device_id: str) -> bool:
        """
        删除设备
        
        Args:
            device_id: 设备ID
            
        Returns:
            是否删除成功
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM devices WHERE device_id = %s",
                    (device_id,)
                )
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        finally:
            conn.close()
    
    def update_device_status(self, device_id: str, status: str) -> bool:
        """
        更新设备状态
        
        Args:
            device_id: 设备ID
            status: 设备状态（online/offline）
            
        Returns:
            是否更新成功
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE devices SET status = %s, last_seen = %s WHERE device_id = %s",
                    (status, datetime.now(), device_id)
                )
                updated = cur.rowcount > 0
                conn.commit()
                return updated
        finally:
            conn.close()
    
    def get_device_count(
        self,
        status: Optional[str] = None,
        os_type: Optional[str] = None
    ) -> int:
        """
        获取设备数量
        
        Args:
            status: 过滤设备状态
            os_type: 过滤操作系统类型
            
        Returns:
            设备数量
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                query = "SELECT COUNT(*) FROM devices WHERE 1=1"
                params = []
                
                if status:
                    query += " AND status = %s"
                    params.append(status)
                
                if os_type:
                    query += " AND os_type = %s"
                    params.append(os_type)
                
                cur.execute(query, params)
                count = cur.fetchone()[0]
                return count
        finally:
            conn.close()


# ==================== API路由 ====================

# 创建路由
router = APIRouter(prefix="/api/v1/devices", tags=["Devices"])

# 全局设备注册管理器实例
_device_manager: Optional[DeviceRegistrationManager] = None


def init_device_manager(database_url: str):
    """初始化全局设备注册管理器实例"""
    global _device_manager
    _device_manager = DeviceRegistrationManager(database_url)


def get_device_manager() -> DeviceRegistrationManager:
    """获取全局设备注册管理器实例"""
    if _device_manager is None:
        raise RuntimeError("DeviceRegistrationManager not initialized")
    return _device_manager


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_device(
    request: DeviceRegisterRequest,
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    注册设备（Agent调用）
    
    设备首次注册时自动生成device_id，后续注册会更新设备信息
    """
    manager = get_device_manager()
    
    try:
        device_info = manager.register_device(
            hostname=request.hostname,
            ip_address=request.ip_address,
            os_type=request.os_type,
            os_version=request.os_version,
            agent_version=request.agent_version,
            metadata=request.metadata
        )
        
        return {
            "status": "success",
            "message": "Device registered successfully",
            "data": device_info
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register device: {str(e)}"
        )


@router.get("", response_model=Dict[str, Any])
async def list_devices(
    status_filter: Optional[str] = Query(None, alias="status", description="过滤设备状态"),
    os_type: Optional[str] = Query(None, description="过滤操作系统类型"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    列出设备
    
    需要 device:read 权限
    """
    # 检查权限
    auth = get_auth_middleware()
    if not auth.check_permissions(auth_info, ["device:read"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: device:read"
        )
    
    manager = get_device_manager()
    
    try:
        devices = manager.list_devices(
            status=status_filter,
            os_type=os_type,
            limit=limit,
            offset=offset
        )
        
        total_count = manager.get_device_count(
            status=status_filter,
            os_type=os_type
        )
        
        return {
            "status": "success",
            "data": {
                "devices": devices,
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list devices: {str(e)}"
        )


@router.get("/{device_id}", response_model=Dict[str, Any])
async def get_device(
    device_id: str,
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    获取设备详情
    
    需要 device:read 权限
    """
    # 检查权限
    auth = get_auth_middleware()
    if not auth.check_permissions(auth_info, ["device:read"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: device:read"
        )
    
    manager = get_device_manager()
    
    device_info = manager.get_device(device_id)
    
    if not device_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )
    
    return {
        "status": "success",
        "data": device_info
    }


@router.put("/{device_id}", response_model=Dict[str, Any])
async def update_device(
    device_id: str,
    request: DeviceUpdateRequest,
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    更新设备信息
    
    需要 device:write 权限
    """
    # 检查权限
    auth = get_auth_middleware()
    if not auth.check_permissions(auth_info, ["device:write"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: device:write"
        )
    
    manager = get_device_manager()
    
    device_info = manager.update_device(
        device_id=device_id,
        device_name=request.device_name,
        description=request.description,
        tags=request.tags,
        metadata=request.metadata
    )
    
    if not device_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )
    
    return {
        "status": "success",
        "message": "Device updated successfully",
        "data": device_info
    }


@router.delete("/{device_id}", response_model=Dict[str, Any])
async def delete_device(
    device_id: str,
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    删除设备
    
    需要 device:delete 权限
    """
    # 检查权限
    auth = get_auth_middleware()
    if not auth.check_permissions(auth_info, ["device:delete"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: device:delete"
        )
    
    manager = get_device_manager()
    
    deleted = manager.delete_device(device_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )
    
    return {
        "status": "success",
        "message": "Device deleted successfully"
    }
