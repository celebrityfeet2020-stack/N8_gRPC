"""
M4-02: 文件上传模块
提供从Hub到Agent的文件上传功能（支持大文件和断点续传）
"""

import os
import uuid
import hashlib
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

# 导入认证依赖
from auth_middleware import verify_session_or_api_key


# ==================== 数据模型 ====================

class FileUploadRequest(BaseModel):
    """文件上传请求"""
    device_id: str = Field(..., description="目标设备ID")
    destination_path: str = Field(..., description="目标路径")
    filename: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    file_hash: Optional[str] = Field(default=None, description="文件MD5哈希")
    overwrite: bool = Field(default=False, description="是否覆盖已存在的文件")
    create_dirs: bool = Field(default=True, description="是否自动创建目录")
    chunk_size: int = Field(default=1048576, description="分块大小（字节，默认1MB）")


class FileUploadTask(BaseModel):
    """文件上传任务"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    destination_path: str = Field(..., description="目标路径")
    filename: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小")
    file_hash: Optional[str] = Field(default=None, description="文件哈希")
    overwrite: bool = Field(..., description="是否覆盖")
    create_dirs: bool = Field(..., description="是否创建目录")
    chunk_size: int = Field(..., description="分块大小")
    status: str = Field(..., description="任务状态: pending, uploading, completed, failed")
    uploaded_size: int = Field(default=0, description="已上传大小")
    progress: float = Field(default=0.0, description="上传进度（0-100）")
    storage_path: Optional[str] = Field(default=None, description="Hub存储路径")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class FileUploadChunk(BaseModel):
    """文件上传分块"""
    task_id: str = Field(..., description="任务ID")
    chunk_index: int = Field(..., description="分块索引（从0开始）")
    chunk_size: int = Field(..., description="分块大小")
    chunk_hash: str = Field(..., description="分块MD5哈希")


class FileUploadResult(BaseModel):
    """文件上传结果"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    destination_path: str = Field(..., description="目标路径")
    filename: str = Field(..., description="文件名")
    status: str = Field(..., description="任务状态")
    file_size: int = Field(..., description="文件大小")
    uploaded_size: int = Field(..., description="已上传大小")
    progress: float = Field(..., description="上传进度")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")


# ==================== 数据库管理器 ====================

class FileUploadManager:
    """文件上传管理器"""
    
    def __init__(self, database_url: str, storage_dir: str = "/tmp/n8_uploads"):
        self.database_url = database_url
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self._init_tables()
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(self.database_url)
    
    def _init_tables(self):
        """初始化数据库表"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 创建文件上传任务表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS file_upload_tasks (
                        task_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        destination_path TEXT NOT NULL,
                        filename VARCHAR(255) NOT NULL,
                        file_size BIGINT NOT NULL,
                        file_hash VARCHAR(64),
                        overwrite BOOLEAN DEFAULT FALSE,
                        create_dirs BOOLEAN DEFAULT TRUE,
                        chunk_size INTEGER DEFAULT 1048576,
                        status VARCHAR(32) DEFAULT 'pending',
                        uploaded_size BIGINT DEFAULT 0,
                        progress FLOAT DEFAULT 0.0,
                        storage_path TEXT,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # 创建文件分块表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS file_upload_chunks (
                        id SERIAL PRIMARY KEY,
                        task_id VARCHAR(64) NOT NULL REFERENCES file_upload_tasks(task_id) ON DELETE CASCADE,
                        chunk_index INTEGER NOT NULL,
                        chunk_size INTEGER NOT NULL,
                        chunk_hash VARCHAR(64),
                        uploaded BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(task_id, chunk_index)
                    )
                """)
                
                # 创建索引
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_upload_tasks_device 
                    ON file_upload_tasks(device_id, created_at DESC)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_upload_tasks_status 
                    ON file_upload_tasks(status, created_at DESC)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_upload_chunks_task 
                    ON file_upload_chunks(task_id, chunk_index)
                """)
                
                conn.commit()
        finally:
            conn.close()
    
    def create_task(self, request: FileUploadRequest) -> str:
        """创建文件上传任务"""
        task_id = f"upload_{uuid.uuid4().hex[:16]}"
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 检查设备是否存在
                cur.execute("SELECT device_id FROM devices WHERE device_id = %s", (request.device_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Device {request.device_id} not found")
                
                # 创建存储路径
                storage_path = os.path.join(self.storage_dir, task_id, request.filename)
                os.makedirs(os.path.dirname(storage_path), exist_ok=True)
                
                # 插入任务
                cur.execute("""
                    INSERT INTO file_upload_tasks 
                    (task_id, device_id, destination_path, filename, file_size, file_hash,
                     overwrite, create_dirs, chunk_size, storage_path, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                """, (
                    task_id,
                    request.device_id,
                    request.destination_path,
                    request.filename,
                    request.file_size,
                    request.file_hash,
                    request.overwrite,
                    request.create_dirs,
                    request.chunk_size,
                    storage_path
                ))
                
                # 计算分块数量
                total_chunks = (request.file_size + request.chunk_size - 1) // request.chunk_size
                
                # 创建分块记录
                for i in range(total_chunks):
                    chunk_size = min(request.chunk_size, request.file_size - i * request.chunk_size)
                    cur.execute("""
                        INSERT INTO file_upload_chunks (task_id, chunk_index, chunk_size)
                        VALUES (%s, %s, %s)
                    """, (task_id, i, chunk_size))
                
                conn.commit()
                return task_id
        finally:
            conn.close()
    
    def upload_chunk(self, task_id: str, chunk_index: int, chunk_data: bytes) -> dict:
        """上传文件分块"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 获取任务信息
                cur.execute("""
                    SELECT task_id, storage_path, chunk_size, file_size
                    FROM file_upload_tasks
                    WHERE task_id = %s
                """, (task_id,))
                
                task = cur.fetchone()
                if not task:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
                
                # 检查分块是否存在
                cur.execute("""
                    SELECT chunk_index, chunk_size, uploaded
                    FROM file_upload_chunks
                    WHERE task_id = %s AND chunk_index = %s
                """, (task_id, chunk_index))
                
                chunk = cur.fetchone()
                if not chunk:
                    raise HTTPException(status_code=404, detail=f"Chunk {chunk_index} not found")
                
                if chunk['uploaded']:
                    return {"message": "Chunk already uploaded", "chunk_index": chunk_index}
                
                # 写入文件
                storage_path = task['storage_path']
                offset = chunk_index * task['chunk_size']
                
                with open(storage_path, 'r+b' if os.path.exists(storage_path) else 'wb') as f:
                    f.seek(offset)
                    f.write(chunk_data)
                
                # 计算分块哈希
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                
                # 更新分块状态
                cur.execute("""
                    UPDATE file_upload_chunks
                    SET uploaded = TRUE, chunk_hash = %s
                    WHERE task_id = %s AND chunk_index = %s
                """, (chunk_hash, task_id, chunk_index))
                
                # 计算上传进度
                cur.execute("""
                    SELECT COUNT(*) as total, 
                           SUM(CASE WHEN uploaded THEN 1 ELSE 0 END) as uploaded
                    FROM file_upload_chunks
                    WHERE task_id = %s
                """, (task_id,))
                
                stats = cur.fetchone()
                progress = (stats['uploaded'] / stats['total']) * 100 if stats['total'] > 0 else 0
                uploaded_size = min(chunk_index * task['chunk_size'] + len(chunk_data), task['file_size'])
                
                # 更新任务进度
                status = 'completed' if stats['uploaded'] == stats['total'] else 'uploading'
                cur.execute("""
                    UPDATE file_upload_tasks
                    SET uploaded_size = %s, progress = %s, status = %s, updated_at = CURRENT_TIMESTAMP,
                        completed_at = CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE task_id = %s
                """, (uploaded_size, progress, status, status, task_id))
                
                conn.commit()
                
                return {
                    "message": "Chunk uploaded successfully",
                    "task_id": task_id,
                    "chunk_index": chunk_index,
                    "progress": progress,
                    "status": status
                }
        finally:
            conn.close()
    
    def get_task(self, task_id: str) -> Optional[FileUploadResult]:
        """获取任务结果"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT task_id, device_id, destination_path, filename, status,
                           file_size, uploaded_size, progress, error_message,
                           created_at, completed_at
                    FROM file_upload_tasks
                    WHERE task_id = %s
                """, (task_id,))
                
                task = cur.fetchone()
                if not task:
                    return None
                
                return FileUploadResult(
                    task_id=task['task_id'],
                    device_id=task['device_id'],
                    destination_path=task['destination_path'],
                    filename=task['filename'],
                    status=task['status'],
                    file_size=task['file_size'],
                    uploaded_size=task['uploaded_size'],
                    progress=task['progress'],
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
    ) -> List[FileUploadTask]:
        """查询任务列表"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT task_id, device_id, destination_path, filename, file_size, file_hash,
                           overwrite, create_dirs, chunk_size, status, uploaded_size, progress,
                           storage_path, created_at, updated_at
                    FROM file_upload_tasks
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
                    tasks.append(FileUploadTask(
                        task_id=row['task_id'],
                        device_id=row['device_id'],
                        destination_path=row['destination_path'],
                        filename=row['filename'],
                        file_size=row['file_size'],
                        file_hash=row['file_hash'],
                        overwrite=row['overwrite'],
                        create_dirs=row['create_dirs'],
                        chunk_size=row['chunk_size'],
                        status=row['status'],
                        uploaded_size=row['uploaded_size'],
                        progress=row['progress'],
                        storage_path=row['storage_path'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    ))
                
                return tasks
        finally:
            conn.close()


# ==================== 全局管理器 ====================

_file_upload_manager: Optional[FileUploadManager] = None


def init_file_upload_manager(database_url: str, storage_dir: str = "/tmp/n8_uploads"):
    """初始化文件上传管理器"""
    global _file_upload_manager
    _file_upload_manager = FileUploadManager(database_url, storage_dir)


def get_file_upload_manager() -> FileUploadManager:
    """获取文件上传管理器"""
    if _file_upload_manager is None:
        raise RuntimeError("FileUploadManager not initialized")
    return _file_upload_manager


# ==================== API路由 ====================

router = APIRouter(prefix="/api/v1/files", tags=["文件管理"])


@router.post("/upload", response_model=dict)
async def create_file_upload_task(
    request: FileUploadRequest,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    创建文件上传任务
    
    - **device_id**: 目标设备ID
    - **destination_path**: 目标路径
    - **filename**: 文件名
    - **file_size**: 文件大小（字节）
    - **file_hash**: 文件MD5哈希（可选）
    - **overwrite**: 是否覆盖已存在的文件
    - **create_dirs**: 是否自动创建目录
    - **chunk_size**: 分块大小（字节，默认1MB）
    
    返回任务ID，需要分块上传文件内容
    """
    manager = get_file_upload_manager()
    task_id = manager.create_task(request)
    
    return {
        "message": "File upload task created successfully",
        "task_id": task_id,
        "device_id": request.device_id,
        "filename": request.filename,
        "status": "pending"
    }


@router.post("/upload/{task_id}/chunk/{chunk_index}", response_model=dict)
async def upload_file_chunk(
    task_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    上传文件分块
    
    - **task_id**: 任务ID
    - **chunk_index**: 分块索引（从0开始）
    - **file**: 分块数据
    
    返回上传进度
    """
    manager = get_file_upload_manager()
    chunk_data = await file.read()
    result = manager.upload_chunk(task_id, chunk_index, chunk_data)
    
    return result


@router.get("/upload/{task_id}", response_model=FileUploadResult)
async def get_file_upload_result(
    task_id: str,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    获取文件上传结果
    
    - **task_id**: 任务ID
    
    返回上传状态和进度
    """
    manager = get_file_upload_manager()
    result = manager.get_task(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return result


@router.get("/upload", response_model=List[FileUploadTask])
async def list_file_upload_tasks(
    device_id: Optional[str] = Query(None, description="设备ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    查询文件上传任务列表
    
    - **device_id**: 设备ID过滤（可选）
    - **status**: 状态过滤（可选）
    - **limit**: 返回数量（1-100）
    - **offset**: 偏移量
    
    返回任务列表
    """
    manager = get_file_upload_manager()
    tasks = manager.list_tasks(device_id=device_id, status=status, limit=limit, offset=offset)
    
    return tasks
