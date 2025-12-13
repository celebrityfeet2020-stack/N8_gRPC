"""
M4-04: 文件操作模块
提供文件复制、移动、删除、重命名等操作
"""

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

class FileOperationRequest(BaseModel):
    """文件操作请求"""
    device_id: str = Field(..., description="设备ID")
    operation: str = Field(..., description="操作类型: copy, move, delete, rename, mkdir, rmdir")
    source_path: str = Field(..., description="源路径")
    destination_path: Optional[str] = Field(default=None, description="目标路径（copy/move/rename需要）")
    recursive: bool = Field(default=False, description="是否递归（delete/rmdir）")
    force: bool = Field(default=False, description="是否强制执行")
    create_dirs: bool = Field(default=True, description="是否自动创建目录（copy/move）")


class FileOperationTask(BaseModel):
    """文件操作任务"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    operation: str = Field(..., description="操作类型")
    source_path: str = Field(..., description="源路径")
    destination_path: Optional[str] = Field(default=None, description="目标路径")
    recursive: bool = Field(..., description="是否递归")
    force: bool = Field(..., description="是否强制")
    create_dirs: bool = Field(..., description="是否创建目录")
    status: str = Field(..., description="任务状态: pending, running, completed, failed")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class FileOperationResult(BaseModel):
    """文件操作结果"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    operation: str = Field(..., description="操作类型")
    source_path: str = Field(..., description="源路径")
    destination_path: Optional[str] = Field(default=None, description="目标路径")
    status: str = Field(..., description="任务状态")
    files_affected: int = Field(default=0, description="影响的文件数量")
    bytes_processed: int = Field(default=0, description="处理的字节数")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")


# ==================== 数据库管理器 ====================

class FileOperationManager:
    """文件操作管理器"""
    
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
                # 创建文件操作任务表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS file_operation_tasks (
                        task_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        operation VARCHAR(32) NOT NULL,
                        source_path TEXT NOT NULL,
                        destination_path TEXT,
                        recursive BOOLEAN DEFAULT FALSE,
                        force BOOLEAN DEFAULT FALSE,
                        create_dirs BOOLEAN DEFAULT TRUE,
                        status VARCHAR(32) DEFAULT 'pending',
                        files_affected INTEGER DEFAULT 0,
                        bytes_processed BIGINT DEFAULT 0,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # 创建索引
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_operation_tasks_device 
                    ON file_operation_tasks(device_id, created_at DESC)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_operation_tasks_status 
                    ON file_operation_tasks(status, created_at DESC)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_operation_tasks_operation 
                    ON file_operation_tasks(operation, created_at DESC)
                """)
                
                conn.commit()
        finally:
            conn.close()
    
    def create_task(self, request: FileOperationRequest) -> str:
        """创建文件操作任务"""
        task_id = f"fileop_{uuid.uuid4().hex[:16]}"
        
        # 验证操作类型
        valid_operations = ['copy', 'move', 'delete', 'rename', 'mkdir', 'rmdir']
        if request.operation not in valid_operations:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid operation: {request.operation}. Must be one of {valid_operations}"
            )
        
        # 验证必需参数
        if request.operation in ['copy', 'move', 'rename']:
            if not request.destination_path:
                raise HTTPException(
                    status_code=400,
                    detail=f"Operation {request.operation} requires destination_path"
                )
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 检查设备是否存在
                cur.execute("SELECT device_id FROM devices WHERE device_id = %s", (request.device_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Device {request.device_id} not found")
                
                # 插入任务
                cur.execute("""
                    INSERT INTO file_operation_tasks 
                    (task_id, device_id, operation, source_path, destination_path,
                     recursive, force, create_dirs, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                """, (
                    task_id,
                    request.device_id,
                    request.operation,
                    request.source_path,
                    request.destination_path,
                    request.recursive,
                    request.force,
                    request.create_dirs
                ))
                
                conn.commit()
                return task_id
        finally:
            conn.close()
    
    def update_task_result(
        self,
        task_id: str,
        status: str,
        files_affected: int = 0,
        bytes_processed: int = 0,
        error_message: Optional[str] = None
    ):
        """更新任务结果（Agent调用）"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE file_operation_tasks
                    SET status = %s, files_affected = %s, bytes_processed = %s,
                        error_message = %s, updated_at = CURRENT_TIMESTAMP,
                        completed_at = CASE WHEN %s IN ('completed', 'failed') 
                                           THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE task_id = %s
                """, (status, files_affected, bytes_processed, error_message, status, task_id))
                
                conn.commit()
        finally:
            conn.close()
    
    def get_task(self, task_id: str) -> Optional[FileOperationResult]:
        """获取任务结果"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT task_id, device_id, operation, source_path, destination_path,
                           status, files_affected, bytes_processed, error_message,
                           created_at, completed_at
                    FROM file_operation_tasks
                    WHERE task_id = %s
                """, (task_id,))
                
                task = cur.fetchone()
                if not task:
                    return None
                
                return FileOperationResult(
                    task_id=task['task_id'],
                    device_id=task['device_id'],
                    operation=task['operation'],
                    source_path=task['source_path'],
                    destination_path=task['destination_path'],
                    status=task['status'],
                    files_affected=task['files_affected'],
                    bytes_processed=task['bytes_processed'],
                    error_message=task['error_message'],
                    created_at=task['created_at'],
                    completed_at=task['completed_at']
                )
        finally:
            conn.close()
    
    def list_tasks(
        self,
        device_id: Optional[str] = None,
        operation: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[FileOperationTask]:
        """查询任务列表"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT task_id, device_id, operation, source_path, destination_path,
                           recursive, force, create_dirs, status, created_at, updated_at
                    FROM file_operation_tasks
                    WHERE 1=1
                """
                params = []
                
                if device_id:
                    query += " AND device_id = %s"
                    params.append(device_id)
                
                if operation:
                    query += " AND operation = %s"
                    params.append(operation)
                
                if status:
                    query += " AND status = %s"
                    params.append(status)
                
                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                
                tasks = []
                for row in cur.fetchall():
                    tasks.append(FileOperationTask(
                        task_id=row['task_id'],
                        device_id=row['device_id'],
                        operation=row['operation'],
                        source_path=row['source_path'],
                        destination_path=row['destination_path'],
                        recursive=row['recursive'],
                        force=row['force'],
                        create_dirs=row['create_dirs'],
                        status=row['status'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    ))
                
                return tasks
        finally:
            conn.close()


# ==================== 全局管理器 ====================

_file_operation_manager: Optional[FileOperationManager] = None


def init_file_operation_manager(database_url: str):
    """初始化文件操作管理器"""
    global _file_operation_manager
    _file_operation_manager = FileOperationManager(database_url)


def get_file_operation_manager() -> FileOperationManager:
    """获取文件操作管理器"""
    if _file_operation_manager is None:
        raise RuntimeError("FileOperationManager not initialized")
    return _file_operation_manager


# ==================== API路由 ====================

router = APIRouter(prefix="/api/v1/files", tags=["文件管理"])


@router.post("/operations", response_model=dict)
async def create_file_operation_task(
    request: FileOperationRequest,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    创建文件操作任务
    
    - **device_id**: 设备ID
    - **operation**: 操作类型（copy, move, delete, rename, mkdir, rmdir）
    - **source_path**: 源路径
    - **destination_path**: 目标路径（copy/move/rename需要）
    - **recursive**: 是否递归（delete/rmdir）
    - **force**: 是否强制执行
    - **create_dirs**: 是否自动创建目录（copy/move）
    
    返回任务ID，Agent需要轮询任务状态获取结果
    """
    manager = get_file_operation_manager()
    task_id = manager.create_task(request)
    
    return {
        "message": "File operation task created successfully",
        "task_id": task_id,
        "device_id": request.device_id,
        "operation": request.operation,
        "status": "pending"
    }


@router.get("/operations/{task_id}", response_model=FileOperationResult)
async def get_file_operation_result(
    task_id: str,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    获取文件操作结果
    
    - **task_id**: 任务ID
    
    返回操作状态和结果
    """
    manager = get_file_operation_manager()
    result = manager.get_task(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return result


@router.get("/operations", response_model=List[FileOperationTask])
async def list_file_operation_tasks(
    device_id: Optional[str] = Query(None, description="设备ID过滤"),
    operation: Optional[str] = Query(None, description="操作类型过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    查询文件操作任务列表
    
    - **device_id**: 设备ID过滤（可选）
    - **operation**: 操作类型过滤（可选）
    - **status**: 状态过滤（可选）
    - **limit**: 返回数量（1-100）
    - **offset**: 偏移量
    
    返回任务列表
    """
    manager = get_file_operation_manager()
    tasks = manager.list_tasks(
        device_id=device_id,
        operation=operation,
        status=status,
        limit=limit,
        offset=offset
    )
    
    return tasks


@router.post("/operations/{task_id}/update", response_model=dict)
async def update_file_operation_result(
    task_id: str,
    status: str = Query(..., description="任务状态"),
    files_affected: int = Query(0, description="影响的文件数"),
    bytes_processed: int = Query(0, description="处理的字节数"),
    error_message: Optional[str] = Query(None, description="错误信息"),
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    更新文件操作结果（Agent调用）
    
    - **task_id**: 任务ID
    - **status**: 任务状态
    - **files_affected**: 影响的文件数
    - **bytes_processed**: 处理的字节数
    - **error_message**: 错误信息
    
    返回更新结果
    """
    manager = get_file_operation_manager()
    manager.update_task_result(task_id, status, files_affected, bytes_processed, error_message)
    
    return {
        "message": "Task result updated successfully",
        "task_id": task_id,
        "status": status
    }
