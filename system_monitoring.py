"""
M6: 系统监控模块
提供系统信息收集、网络信息查询、网络流量监控、进程守护、事件日志、性能历史、网络连接查询功能
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

# 导入认证依赖
from auth_middleware import require_auth


# ==================== 数据模型 ====================

# M6-01: 系统信息收集
class SystemInfo(BaseModel):
    """系统信息"""
    hostname: str = Field(..., description="主机名")
    os_name: str = Field(..., description="操作系统名称")
    os_version: str = Field(..., description="操作系统版本")
    cpu_model: str = Field(..., description="CPU型号")
    cpu_cores: int = Field(..., description="CPU核心数")
    cpu_percent: float = Field(..., description="CPU使用率（%）")
    memory_total_mb: float = Field(..., description="总内存（MB）")
    memory_used_mb: float = Field(..., description="已用内存（MB）")
    memory_percent: float = Field(..., description="内存使用率（%）")
    disk_total_gb: float = Field(..., description="总磁盘空间（GB）")
    disk_used_gb: float = Field(..., description="已用磁盘空间（GB）")
    disk_percent: float = Field(..., description="磁盘使用率（%）")
    boot_time: datetime = Field(..., description="启动时间")
    uptime_seconds: int = Field(..., description="运行时间（秒）")


# M6-02: 网络信息查询
class NetworkInterface(BaseModel):
    """网络接口信息"""
    name: str = Field(..., description="接口名称")
    ip_address: str = Field(..., description="IP地址")
    mac_address: str = Field(..., description="MAC地址")
    netmask: str = Field(default="", description="子网掩码")
    status: str = Field(..., description="状态: up, down")
    speed_mbps: int = Field(default=0, description="速度（Mbps）")


# M6-03: 网络流量监控
class NetworkTraffic(BaseModel):
    """网络流量信息"""
    interface: str = Field(..., description="网络接口")
    bytes_sent: int = Field(..., description="发送字节数")
    bytes_recv: int = Field(..., description="接收字节数")
    packets_sent: int = Field(..., description="发送包数")
    packets_recv: int = Field(..., description="接收包数")
    errors_in: int = Field(default=0, description="接收错误数")
    errors_out: int = Field(default=0, description="发送错误数")
    timestamp: datetime = Field(..., description="时间戳")


# M6-04: 进程守护
class ProcessGuard(BaseModel):
    """进程守护配置"""
    guard_id: str = Field(..., description="守护ID")
    device_id: str = Field(..., description="设备ID")
    process_name: str = Field(..., description="进程名称")
    command: str = Field(..., description="启动命令")
    working_dir: Optional[str] = Field(default=None, description="工作目录")
    check_interval: int = Field(default=60, description="检查间隔（秒）")
    restart_on_failure: bool = Field(default=True, description="失败时重启")
    max_restarts: int = Field(default=3, description="最大重启次数")
    status: str = Field(..., description="状态: active, inactive")
    created_at: datetime = Field(..., description="创建时间")


# M6-05: Windows事件日志
class WindowsEventLog(BaseModel):
    """Windows事件日志"""
    event_id: int = Field(..., description="事件ID")
    level: str = Field(..., description="级别: Information, Warning, Error")
    source: str = Field(..., description="来源")
    message: str = Field(..., description="消息")
    timestamp: datetime = Field(..., description="时间戳")


# M6-06: 设备性能历史
class PerformanceHistory(BaseModel):
    """性能历史记录"""
    device_id: str = Field(..., description="设备ID")
    cpu_percent: float = Field(..., description="CPU使用率（%）")
    memory_percent: float = Field(..., description="内存使用率（%）")
    disk_percent: float = Field(..., description="磁盘使用率（%）")
    network_bytes_sent: int = Field(default=0, description="网络发送字节数")
    network_bytes_recv: int = Field(default=0, description="网络接收字节数")
    timestamp: datetime = Field(..., description="时间戳")


# M6-07: 网络连接查询
class NetworkConnection(BaseModel):
    """网络连接信息"""
    local_address: str = Field(..., description="本地地址")
    local_port: int = Field(..., description="本地端口")
    remote_address: str = Field(..., description="远程地址")
    remote_port: int = Field(..., description="远程端口")
    status: str = Field(..., description="状态: ESTABLISHED, LISTEN, etc")
    pid: int = Field(..., description="进程ID")
    process_name: str = Field(default="", description="进程名称")


# ==================== 数据库管理器 ====================

class SystemMonitoringManager:
    """系统监控管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._init_tables()
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(self.database_url)
    
    def _init_tables(self):
        """初始化数据库表"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # M6-01: 系统信息表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS system_info (
                        id SERIAL PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        hostname TEXT,
                        os_name TEXT,
                        os_version TEXT,
                        cpu_model TEXT,
                        cpu_cores INTEGER,
                        cpu_percent FLOAT,
                        memory_total_mb FLOAT,
                        memory_used_mb FLOAT,
                        memory_percent FLOAT,
                        disk_total_gb FLOAT,
                        disk_used_gb FLOAT,
                        disk_percent FLOAT,
                        boot_time TIMESTAMP,
                        uptime_seconds INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # M6-02: 网络接口表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS network_interfaces (
                        id SERIAL PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        name TEXT NOT NULL,
                        ip_address TEXT,
                        mac_address TEXT,
                        netmask TEXT,
                        status TEXT,
                        speed_mbps INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # M6-03: 网络流量表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS network_traffic (
                        id SERIAL PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        interface TEXT NOT NULL,
                        bytes_sent BIGINT,
                        bytes_recv BIGINT,
                        packets_sent BIGINT,
                        packets_recv BIGINT,
                        errors_in INTEGER,
                        errors_out INTEGER,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # M6-04: 进程守护表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS process_guards (
                        guard_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        process_name TEXT NOT NULL,
                        command TEXT NOT NULL,
                        working_dir TEXT,
                        check_interval INTEGER DEFAULT 60,
                        restart_on_failure BOOLEAN DEFAULT TRUE,
                        max_restarts INTEGER DEFAULT 3,
                        restart_count INTEGER DEFAULT 0,
                        status VARCHAR(32) DEFAULT 'active',
                        last_check TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # M6-05: Windows事件日志表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS windows_event_logs (
                        id SERIAL PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        event_id INTEGER,
                        level TEXT,
                        source TEXT,
                        message TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # M6-06: 性能历史表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS performance_history (
                        id SERIAL PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        cpu_percent FLOAT,
                        memory_percent FLOAT,
                        disk_percent FLOAT,
                        network_bytes_sent BIGINT,
                        network_bytes_recv BIGINT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # M6-07: 网络连接表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS network_connections (
                        id SERIAL PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        local_address TEXT,
                        local_port INTEGER,
                        remote_address TEXT,
                        remote_port INTEGER,
                        status TEXT,
                        pid INTEGER,
                        process_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建索引
                cur.execute("CREATE INDEX IF NOT EXISTS idx_system_info_device ON system_info(device_id, created_at DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_network_interfaces_device ON network_interfaces(device_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_network_traffic_device ON network_traffic(device_id, timestamp DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_process_guards_device ON process_guards(device_id, status)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_windows_event_logs_device ON windows_event_logs(device_id, timestamp DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_performance_history_device ON performance_history(device_id, timestamp DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_network_connections_device ON network_connections(device_id, created_at DESC)")
                
                conn.commit()
        finally:
            conn.close()
    
    # ==================== M6-01: 系统信息收集 ====================
    
    def save_system_info(self, device_id: str, info: SystemInfo):
        """保存系统信息"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO system_info 
                    (device_id, hostname, os_name, os_version, cpu_model, cpu_cores,
                     cpu_percent, memory_total_mb, memory_used_mb, memory_percent,
                     disk_total_gb, disk_used_gb, disk_percent, boot_time, uptime_seconds)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    device_id, info.hostname, info.os_name, info.os_version,
                    info.cpu_model, info.cpu_cores, info.cpu_percent,
                    info.memory_total_mb, info.memory_used_mb, info.memory_percent,
                    info.disk_total_gb, info.disk_used_gb, info.disk_percent,
                    info.boot_time, info.uptime_seconds
                ))
                conn.commit()
        finally:
            conn.close()
    
    def get_latest_system_info(self, device_id: str) -> Optional[SystemInfo]:
        """获取最新系统信息"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM system_info
                    WHERE device_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (device_id,))
                
                row = cur.fetchone()
                if not row:
                    return None
                
                return SystemInfo(
                    hostname=row['hostname'],
                    os_name=row['os_name'],
                    os_version=row['os_version'],
                    cpu_model=row['cpu_model'],
                    cpu_cores=row['cpu_cores'],
                    cpu_percent=row['cpu_percent'],
                    memory_total_mb=row['memory_total_mb'],
                    memory_used_mb=row['memory_used_mb'],
                    memory_percent=row['memory_percent'],
                    disk_total_gb=row['disk_total_gb'],
                    disk_used_gb=row['disk_used_gb'],
                    disk_percent=row['disk_percent'],
                    boot_time=row['boot_time'],
                    uptime_seconds=row['uptime_seconds']
                )
        finally:
            conn.close()
    
    # ==================== M6-02: 网络信息查询 ====================
    
    def save_network_interfaces(self, device_id: str, interfaces: List[NetworkInterface]):
        """保存网络接口信息"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 删除旧数据
                cur.execute("DELETE FROM network_interfaces WHERE device_id = %s", (device_id,))
                
                # 插入新数据
                for iface in interfaces:
                    cur.execute("""
                        INSERT INTO network_interfaces 
                        (device_id, name, ip_address, mac_address, netmask, status, speed_mbps)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        device_id, iface.name, iface.ip_address, iface.mac_address,
                        iface.netmask, iface.status, iface.speed_mbps
                    ))
                
                conn.commit()
        finally:
            conn.close()
    
    def get_network_interfaces(self, device_id: str) -> List[NetworkInterface]:
        """获取网络接口信息"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM network_interfaces
                    WHERE device_id = %s
                    ORDER BY name
                """, (device_id,))
                
                interfaces = []
                for row in cur.fetchall():
                    interfaces.append(NetworkInterface(
                        name=row['name'],
                        ip_address=row['ip_address'],
                        mac_address=row['mac_address'],
                        netmask=row['netmask'],
                        status=row['status'],
                        speed_mbps=row['speed_mbps']
                    ))
                
                return interfaces
        finally:
            conn.close()
    
    # ==================== M6-03: 网络流量监控 ====================
    
    def save_network_traffic(self, device_id: str, traffic: List[NetworkTraffic]):
        """保存网络流量信息"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                for t in traffic:
                    cur.execute("""
                        INSERT INTO network_traffic 
                        (device_id, interface, bytes_sent, bytes_recv, packets_sent,
                         packets_recv, errors_in, errors_out, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        device_id, t.interface, t.bytes_sent, t.bytes_recv,
                        t.packets_sent, t.packets_recv, t.errors_in, t.errors_out,
                        t.timestamp
                    ))
                
                conn.commit()
        finally:
            conn.close()
    
    def get_network_traffic(self, device_id: str, limit: int = 100) -> List[NetworkTraffic]:
        """获取网络流量历史"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM network_traffic
                    WHERE device_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """, (device_id, limit))
                
                traffic_list = []
                for row in cur.fetchall():
                    traffic_list.append(NetworkTraffic(
                        interface=row['interface'],
                        bytes_sent=row['bytes_sent'],
                        bytes_recv=row['bytes_recv'],
                        packets_sent=row['packets_sent'],
                        packets_recv=row['packets_recv'],
                        errors_in=row['errors_in'],
                        errors_out=row['errors_out'],
                        timestamp=row['timestamp']
                    ))
                
                return traffic_list
        finally:
            conn.close()
    
    # ==================== M6-04: 进程守护 ====================
    
    def create_process_guard(self, guard: ProcessGuard) -> str:
        """创建进程守护"""
        guard_id = f"guard_{uuid.uuid4().hex[:16]}"
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO process_guards 
                    (guard_id, device_id, process_name, command, working_dir,
                     check_interval, restart_on_failure, max_restarts, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
                """, (
                    guard_id, guard.device_id, guard.process_name, guard.command,
                    guard.working_dir, guard.check_interval, guard.restart_on_failure,
                    guard.max_restarts
                ))
                
                conn.commit()
                return guard_id
        finally:
            conn.close()
    
    def get_process_guards(self, device_id: str) -> List[ProcessGuard]:
        """获取进程守护列表"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM process_guards
                    WHERE device_id = %s
                    ORDER BY created_at DESC
                """, (device_id,))
                
                guards = []
                for row in cur.fetchall():
                    guards.append(ProcessGuard(
                        guard_id=row['guard_id'],
                        device_id=row['device_id'],
                        process_name=row['process_name'],
                        command=row['command'],
                        working_dir=row['working_dir'],
                        check_interval=row['check_interval'],
                        restart_on_failure=row['restart_on_failure'],
                        max_restarts=row['max_restarts'],
                        status=row['status'],
                        created_at=row['created_at']
                    ))
                
                return guards
        finally:
            conn.close()
    
    # ==================== M6-06: 设备性能历史 ====================
    
    def save_performance_history(self, device_id: str, perf: PerformanceHistory):
        """保存性能历史"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO performance_history 
                    (device_id, cpu_percent, memory_percent, disk_percent,
                     network_bytes_sent, network_bytes_recv, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    device_id, perf.cpu_percent, perf.memory_percent, perf.disk_percent,
                    perf.network_bytes_sent, perf.network_bytes_recv, perf.timestamp
                ))
                
                conn.commit()
        finally:
            conn.close()
    
    def get_performance_history(self, device_id: str, hours: int = 24) -> List[PerformanceHistory]:
        """获取性能历史"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM performance_history
                    WHERE device_id = %s
                      AND timestamp >= NOW() - INTERVAL '%s hours'
                    ORDER BY timestamp DESC
                """, (device_id, hours))
                
                history = []
                for row in cur.fetchall():
                    history.append(PerformanceHistory(
                        device_id=row['device_id'],
                        cpu_percent=row['cpu_percent'],
                        memory_percent=row['memory_percent'],
                        disk_percent=row['disk_percent'],
                        network_bytes_sent=row['network_bytes_sent'],
                        network_bytes_recv=row['network_bytes_recv'],
                        timestamp=row['timestamp']
                    ))
                
                return history
        finally:
            conn.close()
    
    # ==================== M6-07: 网络连接查询 ====================
    
    def save_network_connections(self, device_id: str, connections: List[NetworkConnection]):
        """保存网络连接信息"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 删除旧数据
                cur.execute("DELETE FROM network_connections WHERE device_id = %s", (device_id,))
                
                # 插入新数据
                for conn_info in connections:
                    cur.execute("""
                        INSERT INTO network_connections 
                        (device_id, local_address, local_port, remote_address, remote_port,
                         status, pid, process_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        device_id, conn_info.local_address, conn_info.local_port,
                        conn_info.remote_address, conn_info.remote_port,
                        conn_info.status, conn_info.pid, conn_info.process_name
                    ))
                
                conn.commit()
        finally:
            conn.close()
    
    def get_network_connections(self, device_id: str) -> List[NetworkConnection]:
        """获取网络连接信息"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM network_connections
                    WHERE device_id = %s
                    ORDER BY created_at DESC
                """, (device_id,))
                
                connections = []
                for row in cur.fetchall():
                    connections.append(NetworkConnection(
                        local_address=row['local_address'],
                        local_port=row['local_port'],
                        remote_address=row['remote_address'],
                        remote_port=row['remote_port'],
                        status=row['status'],
                        pid=row['pid'],
                        process_name=row['process_name']
                    ))
                
                return connections
        finally:
            conn.close()


# ==================== 全局管理器 ====================

_system_monitoring_manager: Optional[SystemMonitoringManager] = None


def init_system_monitoring_manager(database_url: str):
    """初始化系统监控管理器"""
    global _system_monitoring_manager
    _system_monitoring_manager = SystemMonitoringManager(database_url)


def get_system_monitoring_manager() -> SystemMonitoringManager:
    """获取系统监控管理器"""
    if _system_monitoring_manager is None:
        raise RuntimeError("SystemMonitoringManager not initialized")
    return _system_monitoring_manager


# ==================== API路由 ====================

router = APIRouter(prefix="/api/v1/monitoring", tags=["系统监控"])


# ==================== M6-01: 系统信息收集 ====================

@router.post("/system-info/{device_id}", response_model=dict)
async def upload_system_info(
    device_id: str,
    info: SystemInfo,
    auth_info: dict = Depends(require_auth)
):
    """上传系统信息（Agent调用）"""
    manager = get_system_monitoring_manager()
    manager.save_system_info(device_id, info)
    
    return {"message": "System info uploaded successfully", "device_id": device_id}


@router.get("/system-info/{device_id}", response_model=SystemInfo)
async def get_system_info(
    device_id: str,
    auth_info: dict = Depends(require_auth)
):
    """获取系统信息"""
    manager = get_system_monitoring_manager()
    info = manager.get_latest_system_info(device_id)
    
    if not info:
        raise HTTPException(status_code=404, detail=f"No system info found for device {device_id}")
    
    return info


# ==================== M6-02: 网络信息查询 ====================

@router.post("/network-interfaces/{device_id}", response_model=dict)
async def upload_network_interfaces(
    device_id: str,
    interfaces: List[NetworkInterface],
    auth_info: dict = Depends(require_auth)
):
    """上传网络接口信息（Agent调用）"""
    manager = get_system_monitoring_manager()
    manager.save_network_interfaces(device_id, interfaces)
    
    return {"message": "Network interfaces uploaded successfully", "count": len(interfaces)}


@router.get("/network-interfaces/{device_id}", response_model=List[NetworkInterface])
async def get_network_interfaces(
    device_id: str,
    auth_info: dict = Depends(require_auth)
):
    """获取网络接口信息"""
    manager = get_system_monitoring_manager()
    interfaces = manager.get_network_interfaces(device_id)
    
    return interfaces


# ==================== M6-03: 网络流量监控 ====================

@router.post("/network-traffic/{device_id}", response_model=dict)
async def upload_network_traffic(
    device_id: str,
    traffic: List[NetworkTraffic],
    auth_info: dict = Depends(require_auth)
):
    """上传网络流量信息（Agent调用）"""
    manager = get_system_monitoring_manager()
    manager.save_network_traffic(device_id, traffic)
    
    return {"message": "Network traffic uploaded successfully", "count": len(traffic)}


@router.get("/network-traffic/{device_id}", response_model=List[NetworkTraffic])
async def get_network_traffic(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    auth_info: dict = Depends(require_auth)
):
    """获取网络流量历史"""
    manager = get_system_monitoring_manager()
    traffic = manager.get_network_traffic(device_id, limit)
    
    return traffic


# ==================== M6-04: 进程守护 ====================

@router.post("/process-guards", response_model=dict)
async def create_process_guard(
    guard: ProcessGuard,
    auth_info: dict = Depends(require_auth)
):
    """创建进程守护"""
    manager = get_system_monitoring_manager()
    guard_id = manager.create_process_guard(guard)
    
    return {"message": "Process guard created successfully", "guard_id": guard_id}


@router.get("/process-guards/{device_id}", response_model=List[ProcessGuard])
async def get_process_guards(
    device_id: str,
    auth_info: dict = Depends(require_auth)
):
    """获取进程守护列表"""
    manager = get_system_monitoring_manager()
    guards = manager.get_process_guards(device_id)
    
    return guards


# ==================== M6-06: 设备性能历史 ====================

@router.post("/performance-history/{device_id}", response_model=dict)
async def upload_performance_history(
    device_id: str,
    perf: PerformanceHistory,
    auth_info: dict = Depends(require_auth)
):
    """上传性能历史（Agent调用）"""
    manager = get_system_monitoring_manager()
    manager.save_performance_history(device_id, perf)
    
    return {"message": "Performance history uploaded successfully"}


@router.get("/performance-history/{device_id}", response_model=List[PerformanceHistory])
async def get_performance_history(
    device_id: str,
    hours: int = Query(24, ge=1, le=168, description="小时数"),
    auth_info: dict = Depends(require_auth)
):
    """获取性能历史"""
    manager = get_system_monitoring_manager()
    history = manager.get_performance_history(device_id, hours)
    
    return history


# ==================== M6-07: 网络连接查询 ====================

@router.post("/network-connections/{device_id}", response_model=dict)
async def upload_network_connections(
    device_id: str,
    connections: List[NetworkConnection],
    auth_info: dict = Depends(require_auth)
):
    """上传网络连接信息（Agent调用）"""
    manager = get_system_monitoring_manager()
    manager.save_network_connections(device_id, connections)
    
    return {"message": "Network connections uploaded successfully", "count": len(connections)}


@router.get("/network-connections/{device_id}", response_model=List[NetworkConnection])
async def get_network_connections(
    device_id: str,
    auth_info: dict = Depends(require_auth)
):
    """获取网络连接信息"""
    manager = get_system_monitoring_manager()
    connections = manager.get_network_connections(device_id)
    
    return connections
