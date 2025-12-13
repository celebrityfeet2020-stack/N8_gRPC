"""
M5: 进程管理模块
提供进程列表查询、进程终止、进程启动、进程详情查询功能
"""

import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

# 导入认证依赖
from auth_middleware import require_auth


# ==================== 数据模型 ====================

class ProcessInfo(BaseModel):
    """进程信息"""
    pid: int = Field(..., description="进程ID")
    name: str = Field(..., description="进程名称")
    cpu_percent: float = Field(default=0.0, description="CPU使用率（%）")
    memory_percent: float = Field(default=0.0, description="内存使用率（%）")
    memory_mb: float = Field(default=0.0, description="内存使用量（MB）")
    status: str = Field(default="", description="进程状态")
    username: str = Field(default="", description="用户名")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")
    cmdline: str = Field(default="", description="命令行")


class ProcessListRequest(BaseModel):
    """进程列表查询请求"""
    device_id: str = Field(..., description="设备ID")
    name_filter: Optional[str] = Field(default=None, description="进程名称过滤")
    sort_by: str = Field(default="cpu", description="排序字段: cpu, memory, pid, name")
    sort_order: str = Field(default="desc", description="排序方向: asc, desc")
    limit: int = Field(default=100, description="返回数量")


class ProcessListTask(BaseModel):
    """进程列表查询任务"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    name_filter: Optional[str] = Field(default=None, description="进程名称过滤")
    sort_by: str = Field(..., description="排序字段")
    sort_order: str = Field(..., description="排序方向")
    limit: int = Field(..., description="返回数量")
    status: str = Field(..., description="任务状态: pending, completed, failed")
    process_count: int = Field(default=0, description="进程数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class ProcessKillRequest(BaseModel):
    """进程终止请求"""
    device_id: str = Field(..., description="设备ID")
    pid: int = Field(..., description="进程ID")
    force: bool = Field(default=False, description="是否强制终止")


class ProcessStartRequest(BaseModel):
    """进程启动请求"""
    device_id: str = Field(..., description="设备ID")
    command: str = Field(..., description="启动命令")
    working_dir: Optional[str] = Field(default=None, description="工作目录")
    env_vars: Optional[dict] = Field(default=None, description="环境变量")


class ProcessActionTask(BaseModel):
    """进程操作任务"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    action: str = Field(..., description="操作类型: kill, start")
    pid: Optional[int] = Field(default=None, description="进程ID（kill操作）")
    command: Optional[str] = Field(default=None, description="启动命令（start操作）")
    force: bool = Field(default=False, description="是否强制")
    status: str = Field(..., description="任务状态: pending, completed, failed")
    result_pid: Optional[int] = Field(default=None, description="结果进程ID（start操作）")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")


# ==================== 数据库管理器 ====================

class ProcessManager:
    """进程管理器"""
    
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
                # 创建进程列表任务表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS process_list_tasks (
                        task_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        name_filter TEXT,
                        sort_by VARCHAR(32) DEFAULT 'cpu',
                        sort_order VARCHAR(8) DEFAULT 'desc',
                        limit_count INTEGER DEFAULT 100,
                        status VARCHAR(32) DEFAULT 'pending',
                        process_count INTEGER DEFAULT 0,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # 创建进程信息表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS process_list_results (
                        id SERIAL PRIMARY KEY,
                        task_id VARCHAR(64) NOT NULL REFERENCES process_list_tasks(task_id) ON DELETE CASCADE,
                        pid INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        cpu_percent FLOAT DEFAULT 0.0,
                        memory_percent FLOAT DEFAULT 0.0,
                        memory_mb FLOAT DEFAULT 0.0,
                        status TEXT,
                        username TEXT,
                        create_time TIMESTAMP,
                        cmdline TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建进程操作任务表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS process_action_tasks (
                        task_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        action VARCHAR(32) NOT NULL,
                        pid INTEGER,
                        command TEXT,
                        working_dir TEXT,
                        env_vars JSONB,
                        force BOOLEAN DEFAULT FALSE,
                        status VARCHAR(32) DEFAULT 'pending',
                        result_pid INTEGER,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # 创建索引
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_process_list_tasks_device 
                    ON process_list_tasks(device_id, created_at DESC)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_process_list_results_task 
                    ON process_list_results(task_id)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_process_action_tasks_device 
                    ON process_action_tasks(device_id, created_at DESC)
                """)
                
                conn.commit()
        finally:
            conn.close()
    
    # ==================== M5-01: 进程列表查询 ====================
    
    def create_list_task(self, request: ProcessListRequest) -> str:
        """创建进程列表查询任务"""
        task_id = f"proclist_{uuid.uuid4().hex[:16]}"
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 检查设备是否存在
                cur.execute("SELECT device_id FROM devices WHERE device_id = %s", (request.device_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Device {request.device_id} not found")
                
                # 插入任务
                cur.execute("""
                    INSERT INTO process_list_tasks 
                    (task_id, device_id, name_filter, sort_by, sort_order, limit_count, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                """, (
                    task_id,
                    request.device_id,
                    request.name_filter,
                    request.sort_by,
                    request.sort_order,
                    request.limit
                ))
                
                conn.commit()
                return task_id
        finally:
            conn.close()
    
    def update_list_results(self, task_id: str, processes: List[ProcessInfo]):
        """更新进程列表结果（Agent调用）"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 插入进程信息
                for proc in processes:
                    cur.execute("""
                        INSERT INTO process_list_results 
                        (task_id, pid, name, cpu_percent, memory_percent, memory_mb,
                         status, username, create_time, cmdline)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id,
                        proc.pid,
                        proc.name,
                        proc.cpu_percent,
                        proc.memory_percent,
                        proc.memory_mb,
                        proc.status,
                        proc.username,
                        proc.create_time,
                        proc.cmdline
                    ))
                
                # 更新任务状态
                cur.execute("""
                    UPDATE process_list_tasks
                    SET status = 'completed', process_count = %s, 
                        updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                    WHERE task_id = %s
                """, (len(processes), task_id))
                
                conn.commit()
        finally:
            conn.close()
    
    def get_list_results(self, task_id: str) -> List[ProcessInfo]:
        """获取进程列表结果"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT pid, name, cpu_percent, memory_percent, memory_mb,
                           status, username, create_time, cmdline
                    FROM process_list_results
                    WHERE task_id = %s
                    ORDER BY cpu_percent DESC
                """, (task_id,))
                
                processes = []
                for row in cur.fetchall():
                    processes.append(ProcessInfo(
                        pid=row['pid'],
                        name=row['name'],
                        cpu_percent=row['cpu_percent'],
                        memory_percent=row['memory_percent'],
                        memory_mb=row['memory_mb'],
                        status=row['status'],
                        username=row['username'],
                        create_time=row['create_time'],
                        cmdline=row['cmdline']
                    ))
                
                return processes
        finally:
            conn.close()
    
    # ==================== M5-02: 进程终止 ====================
    
    def create_kill_task(self, request: ProcessKillRequest) -> str:
        """创建进程终止任务"""
        task_id = f"prockill_{uuid.uuid4().hex[:16]}"
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 检查设备是否存在
                cur.execute("SELECT device_id FROM devices WHERE device_id = %s", (request.device_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Device {request.device_id} not found")
                
                # 插入任务
                cur.execute("""
                    INSERT INTO process_action_tasks 
                    (task_id, device_id, action, pid, force, status)
                    VALUES (%s, %s, 'kill', %s, %s, 'pending')
                """, (task_id, request.device_id, request.pid, request.force))
                
                conn.commit()
                return task_id
        finally:
            conn.close()
    
    # ==================== M5-03: 进程启动 ====================
    
    def create_start_task(self, request: ProcessStartRequest) -> str:
        """创建进程启动任务"""
        task_id = f"procstart_{uuid.uuid4().hex[:16]}"
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 检查设备是否存在
                cur.execute("SELECT device_id FROM devices WHERE device_id = %s", (request.device_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Device {request.device_id} not found")
                
                # 插入任务
                cur.execute("""
                    INSERT INTO process_action_tasks 
                    (task_id, device_id, action, command, working_dir, env_vars, status)
                    VALUES (%s, %s, 'start', %s, %s, %s, 'pending')
                """, (
                    task_id,
                    request.device_id,
                    request.command,
                    request.working_dir,
                    psycopg2.extras.Json(request.env_vars) if request.env_vars else None
                ))
                
                conn.commit()
                return task_id
        finally:
            conn.close()
    
    # ==================== M5-04: 进程详情查询 ====================
    
    def get_process_detail(self, task_id: str, pid: int) -> Optional[ProcessInfo]:
        """获取进程详情"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT pid, name, cpu_percent, memory_percent, memory_mb,
                           status, username, create_time, cmdline
                    FROM process_list_results
                    WHERE task_id = %s AND pid = %s
                """, (task_id, pid))
                
                row = cur.fetchone()
                if not row:
                    return None
                
                return ProcessInfo(
                    pid=row['pid'],
                    name=row['name'],
                    cpu_percent=row['cpu_percent'],
                    memory_percent=row['memory_percent'],
                    memory_mb=row['memory_mb'],
                    status=row['status'],
                    username=row['username'],
                    create_time=row['create_time'],
                    cmdline=row['cmdline']
                )
        finally:
            conn.close()
    
    # ==================== 通用方法 ====================
    
    def update_action_result(
        self,
        task_id: str,
        status: str,
        result_pid: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """更新操作任务结果（Agent调用）"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE process_action_tasks
                    SET status = %s, result_pid = %s, error_message = %s,
                        updated_at = CURRENT_TIMESTAMP,
                        completed_at = CASE WHEN %s IN ('completed', 'failed') 
                                           THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE task_id = %s
                """, (status, result_pid, error_message, status, task_id))
                
                conn.commit()
        finally:
            conn.close()
    
    def get_action_task(self, task_id: str) -> Optional[ProcessActionTask]:
        """获取操作任务"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT task_id, device_id, action, pid, command, force,
                           status, result_pid, error_message, created_at, completed_at
                    FROM process_action_tasks
                    WHERE task_id = %s
                """, (task_id,))
                
                row = cur.fetchone()
                if not row:
                    return None
                
                return ProcessActionTask(
                    task_id=row['task_id'],
                    device_id=row['device_id'],
                    action=row['action'],
                    pid=row['pid'],
                    command=row['command'],
                    force=row['force'],
                    status=row['status'],
                    result_pid=row['result_pid'],
                    error_message=row['error_message'],
                    created_at=row['created_at'],
                    completed_at=row['completed_at']
                )
        finally:
            conn.close()


# ==================== 全局管理器 ====================

_process_manager: Optional[ProcessManager] = None


def init_process_manager(database_url: str):
    """初始化进程管理器"""
    global _process_manager
    _process_manager = ProcessManager(database_url)


def get_process_manager() -> ProcessManager:
    """获取进程管理器"""
    if _process_manager is None:
        raise RuntimeError("ProcessManager not initialized")
    return _process_manager


# ==================== API路由 ====================

router = APIRouter(prefix="/api/v1/processes", tags=["进程管理"])


# ==================== M5-01: 进程列表查询 ====================

@router.post("/list", response_model=dict)
async def create_process_list_task(
    request: ProcessListRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    创建进程列表查询任务
    
    - **device_id**: 设备ID
    - **name_filter**: 进程名称过滤（可选）
    - **sort_by**: 排序字段（cpu, memory, pid, name）
    - **sort_order**: 排序方向（asc, desc）
    - **limit**: 返回数量
    
    返回任务ID，Agent需要上传进程列表
    """
    manager = get_process_manager()
    task_id = manager.create_list_task(request)
    
    return {
        "message": "Process list task created successfully",
        "task_id": task_id,
        "device_id": request.device_id,
        "status": "pending"
    }


@router.get("/list/{task_id}", response_model=List[ProcessInfo])
async def get_process_list_results(
    task_id: str,
    auth_info: dict = Depends(require_auth)
):
    """
    获取进程列表结果
    
    - **task_id**: 任务ID
    
    返回进程列表
    """
    manager = get_process_manager()
    processes = manager.get_list_results(task_id)
    
    return processes


@router.post("/list/{task_id}/upload", response_model=dict)
async def upload_process_list(
    task_id: str,
    processes: List[ProcessInfo],
    auth_info: dict = Depends(require_auth)
):
    """
    上传进程列表（Agent调用）
    
    - **task_id**: 任务ID
    - **processes**: 进程列表
    
    返回上传结果
    """
    manager = get_process_manager()
    manager.update_list_results(task_id, processes)
    
    return {
        "message": "Process list uploaded successfully",
        "task_id": task_id,
        "process_count": len(processes)
    }


# ==================== M5-02: 进程终止 ====================

@router.post("/kill", response_model=dict)
async def create_process_kill_task(
    request: ProcessKillRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    创建进程终止任务
    
    - **device_id**: 设备ID
    - **pid**: 进程ID
    - **force**: 是否强制终止
    
    返回任务ID，Agent需要执行终止操作
    """
    manager = get_process_manager()
    task_id = manager.create_kill_task(request)
    
    return {
        "message": "Process kill task created successfully",
        "task_id": task_id,
        "device_id": request.device_id,
        "pid": request.pid,
        "status": "pending"
    }


# ==================== M5-03: 进程启动 ====================

@router.post("/start", response_model=dict)
async def create_process_start_task(
    request: ProcessStartRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    创建进程启动任务
    
    - **device_id**: 设备ID
    - **command**: 启动命令
    - **working_dir**: 工作目录（可选）
    - **env_vars**: 环境变量（可选）
    
    返回任务ID，Agent需要执行启动操作
    """
    manager = get_process_manager()
    task_id = manager.create_start_task(request)
    
    return {
        "message": "Process start task created successfully",
        "task_id": task_id,
        "device_id": request.device_id,
        "command": request.command,
        "status": "pending"
    }


# ==================== M5-04: 进程详情查询 ====================

@router.get("/detail/{task_id}/{pid}", response_model=ProcessInfo)
async def get_process_detail(
    task_id: str,
    pid: int,
    auth_info: dict = Depends(require_auth)
):
    """
    获取进程详情
    
    - **task_id**: 任务ID（来自进程列表查询）
    - **pid**: 进程ID
    
    返回进程详细信息
    """
    manager = get_process_manager()
    process = manager.get_process_detail(task_id, pid)
    
    if not process:
        raise HTTPException(status_code=404, detail=f"Process {pid} not found in task {task_id}")
    
    return process


# ==================== 通用接口 ====================

@router.get("/action/{task_id}", response_model=ProcessActionTask)
async def get_process_action_result(
    task_id: str,
    auth_info: dict = Depends(require_auth)
):
    """
    获取进程操作结果
    
    - **task_id**: 任务ID
    
    返回操作状态和结果
    """
    manager = get_process_manager()
    task = manager.get_action_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return task


@router.post("/action/{task_id}/update", response_model=dict)
async def update_process_action_result(
    task_id: str,
    status: str = Query(..., description="任务状态"),
    result_pid: Optional[int] = Query(None, description="结果进程ID"),
    error_message: Optional[str] = Query(None, description="错误信息"),
    auth_info: dict = Depends(require_auth)
):
    """
    更新进程操作结果（Agent调用）
    
    - **task_id**: 任务ID
    - **status**: 任务状态
    - **result_pid**: 结果进程ID（start操作）
    - **error_message**: 错误信息
    
    返回更新结果
    """
    manager = get_process_manager()
    manager.update_action_result(task_id, status, result_pid, error_message)
    
    return {
        "message": "Action result updated successfully",
        "task_id": task_id,
        "status": status
    }
