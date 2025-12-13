"""
M4-01: 文件列表查询模块
提供远程设备文件系统浏览功能
"""

import os
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

# 导入认证依赖
from auth_middleware import verify_session_or_api_key


# ==================== 数据模型 ====================

class FileListRequest(BaseModel):
    """文件列表查询请求"""
    device_id: str = Field(..., description="设备ID")
    path: str = Field(default="/", description="查询路径")
    recursive: bool = Field(default=False, description="是否递归查询子目录")
    include_hidden: bool = Field(default=False, description="是否包含隐藏文件")
    file_types: Optional[List[str]] = Field(default=None, description="文件类型过滤（如: ['.txt', '.pdf']）")
    sort_by: str = Field(default="name", description="排序字段: name, size, modified_time")
    sort_order: str = Field(default="asc", description="排序方向: asc, desc")
    max_depth: int = Field(default=5, description="递归最大深度")


class FileListTask(BaseModel):
    """文件列表任务"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    path: str = Field(..., description="查询路径")
    recursive: bool = Field(..., description="是否递归")
    include_hidden: bool = Field(..., description="是否包含隐藏文件")
    file_types: Optional[List[str]] = Field(default=None, description="文件类型过滤")
    sort_by: str = Field(..., description="排序字段")
    sort_order: str = Field(..., description="排序方向")
    max_depth: int = Field(..., description="最大深度")
    status: str = Field(..., description="任务状态: pending, running, completed, failed")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class FileInfo(BaseModel):
    """文件信息"""
    name: str = Field(..., description="文件名")
    path: str = Field(..., description="完整路径")
    type: str = Field(..., description="类型: file, directory")
    size: int = Field(..., description="文件大小（字节）")
    modified_time: datetime = Field(..., description="修改时间")
    permissions: Optional[str] = Field(default=None, description="权限（Unix格式）")
    owner: Optional[str] = Field(default=None, description="所有者")


class FileListResult(BaseModel):
    """文件列表结果"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    path: str = Field(..., description="查询路径")
    status: str = Field(..., description="任务状态")
    total_files: int = Field(default=0, description="文件总数")
    total_directories: int = Field(default=0, description="目录总数")
    total_size: int = Field(default=0, description="总大小（字节）")
    files: List[FileInfo] = Field(default=[], description="文件列表")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")


# ==================== 数据库管理器 ====================

class FileListManager:
    """文件列表管理器"""
    
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
                # 创建文件列表任务表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS file_list_tasks (
                        task_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        path TEXT NOT NULL,
                        recursive BOOLEAN DEFAULT FALSE,
                        include_hidden BOOLEAN DEFAULT FALSE,
                        file_types JSONB,
                        sort_by VARCHAR(32) DEFAULT 'name',
                        sort_order VARCHAR(8) DEFAULT 'asc',
                        max_depth INTEGER DEFAULT 5,
                        status VARCHAR(32) DEFAULT 'pending',
                        total_files INTEGER DEFAULT 0,
                        total_directories INTEGER DEFAULT 0,
                        total_size BIGINT DEFAULT 0,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # 创建文件信息表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS file_list_results (
                        id SERIAL PRIMARY KEY,
                        task_id VARCHAR(64) NOT NULL REFERENCES file_list_tasks(task_id) ON DELETE CASCADE,
                        name TEXT NOT NULL,
                        path TEXT NOT NULL,
                        type VARCHAR(16) NOT NULL,
                        size BIGINT DEFAULT 0,
                        modified_time TIMESTAMP,
                        permissions VARCHAR(16),
                        owner VARCHAR(64),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建索引
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_list_tasks_device 
                    ON file_list_tasks(device_id, created_at DESC)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_list_tasks_status 
                    ON file_list_tasks(status, created_at DESC)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_list_results_task 
                    ON file_list_results(task_id)
                """)
                
                conn.commit()
        finally:
            conn.close()
    
    def create_task(self, request: FileListRequest) -> str:
        """创建文件列表任务"""
        task_id = f"filelist_{uuid.uuid4().hex[:16]}"
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 检查设备是否存在
                cur.execute("SELECT device_id FROM devices WHERE device_id = %s", (request.device_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Device {request.device_id} not found")
                
                # 插入任务
                cur.execute("""
                    INSERT INTO file_list_tasks 
                    (task_id, device_id, path, recursive, include_hidden, file_types, 
                     sort_by, sort_order, max_depth, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                """, (
                    task_id,
                    request.device_id,
                    request.path,
                    request.recursive,
                    request.include_hidden,
                    psycopg2.extras.Json(request.file_types) if request.file_types else None,
                    request.sort_by,
                    request.sort_order,
                    request.max_depth
                ))
                
                conn.commit()
                return task_id
        finally:
            conn.close()
    
    def get_task(self, task_id: str) -> Optional[FileListResult]:
        """获取任务结果"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 获取任务信息
                cur.execute("""
                    SELECT task_id, device_id, path, status, total_files, total_directories,
                           total_size, error_message, created_at, completed_at
                    FROM file_list_tasks
                    WHERE task_id = %s
                """, (task_id,))
                
                task = cur.fetchone()
                if not task:
                    return None
                
                # 获取文件列表
                cur.execute("""
                    SELECT name, path, type, size, modified_time, permissions, owner
                    FROM file_list_results
                    WHERE task_id = %s
                    ORDER BY type DESC, name ASC
                """, (task_id,))
                
                files = []
                for row in cur.fetchall():
                    files.append(FileInfo(
                        name=row['name'],
                        path=row['path'],
                        type=row['type'],
                        size=row['size'],
                        modified_time=row['modified_time'],
                        permissions=row['permissions'],
                        owner=row['owner']
                    ))
                
                return FileListResult(
                    task_id=task['task_id'],
                    device_id=task['device_id'],
                    path=task['path'],
                    status=task['status'],
                    total_files=task['total_files'],
                    total_directories=task['total_directories'],
                    total_size=task['total_size'],
                    files=files,
                    error_message=task['error_message'],
                    created_at=task['created_at'],
                    completed_at=task['completed_at']
                )
        finally:
            conn.close()
    
    def list_tasks(
        self,
        device_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[FileListTask]:
        """查询任务列表"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT task_id, device_id, path, recursive, include_hidden, file_types,
                           sort_by, sort_order, max_depth, status, created_at, updated_at
                    FROM file_list_tasks
                    WHERE 1=1
                """
                params = []
                
                if device_id:
                    query += " AND device_id = %s"
                    params.append(device_id)
                
                if status:
                    query += " AND status = %s"
                    params.append(status)
                
                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                
                tasks = []
                for row in cur.fetchall():
                    tasks.append(FileListTask(
                        task_id=row['task_id'],
                        device_id=row['device_id'],
                        path=row['path'],
                        recursive=row['recursive'],
                        include_hidden=row['include_hidden'],
                        file_types=row['file_types'],
                        sort_by=row['sort_by'],
                        sort_order=row['sort_order'],
                        max_depth=row['max_depth'],
                        status=row['status'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    ))
                
                return tasks
        finally:
            conn.close()


# ==================== 全局管理器 ====================

_file_list_manager: Optional[FileListManager] = None


def init_file_list_manager(database_url: str):
    """初始化文件列表管理器"""
    global _file_list_manager
    _file_list_manager = FileListManager(database_url)


def get_file_list_manager() -> FileListManager:
    """获取文件列表管理器"""
    if _file_list_manager is None:
        raise RuntimeError("FileListManager not initialized")
    return _file_list_manager


# ==================== API路由 ====================

router = APIRouter(prefix="/api/v1/files", tags=["文件管理"])


@router.post("/list", response_model=dict)
async def create_file_list_task(
    request: FileListRequest,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    创建文件列表查询任务
    
    - **device_id**: 设备ID
    - **path**: 查询路径（默认: /）
    - **recursive**: 是否递归查询子目录
    - **include_hidden**: 是否包含隐藏文件
    - **file_types**: 文件类型过滤（如: ['.txt', '.pdf']）
    - **sort_by**: 排序字段（name, size, modified_time）
    - **sort_order**: 排序方向（asc, desc）
    - **max_depth**: 递归最大深度
    
    返回任务ID，Agent需要轮询任务状态获取结果
    """
    manager = get_file_list_manager()
    task_id = manager.create_task(request)
    
    return {
        "message": "File list task created successfully",
        "task_id": task_id,
        "device_id": request.device_id,
        "path": request.path,
        "status": "pending"
    }


@router.get("/list/{task_id}", response_model=FileListResult)
async def get_file_list_result(
    task_id: str,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    获取文件列表查询结果
    
    - **task_id**: 任务ID
    
    返回文件列表和统计信息
    """
    manager = get_file_list_manager()
    result = manager.get_task(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return result


@router.get("/list", response_model=List[FileListTask])
async def list_file_list_tasks(
    device_id: Optional[str] = Query(None, description="设备ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    查询文件列表任务列表
    
    - **device_id**: 设备ID过滤（可选）
    - **status**: 状态过滤（可选）
    - **limit**: 返回数量（1-100）
    - **offset**: 偏移量
    
    返回任务列表
    """
    manager = get_file_list_manager()
    tasks = manager.list_tasks(device_id=device_id, status=status, limit=limit, offset=offset)
    
    return tasks
