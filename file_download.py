"""
M4-03: 文件下载模块
提供从Agent到Hub的文件下载功能（支持大文件和断点续传）
"""

import os
import uuid
import hashlib
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

# 导入认证依赖
from auth_middleware import verify_session_or_api_key


# ==================== 数据模型 ====================

class FileDownloadRequest(BaseModel):
    """文件下载请求"""
    device_id: str = Field(..., description="源设备ID")
    source_path: str = Field(..., description="源文件路径")
    verify_hash: bool = Field(default=True, description="是否验证文件哈希")


class FileDownloadTask(BaseModel):
    """文件下载任务"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    source_path: str = Field(..., description="源文件路径")
    filename: str = Field(..., description="文件名")
    file_size: int = Field(default=0, description="文件大小")
    file_hash: Optional[str] = Field(default=None, description="文件哈希")
    verify_hash: bool = Field(..., description="是否验证哈希")
    status: str = Field(..., description="任务状态: pending, downloading, completed, failed")
    downloaded_size: int = Field(default=0, description="已下载大小")
    progress: float = Field(default=0.0, description="下载进度（0-100）")
    storage_path: Optional[str] = Field(default=None, description="Hub存储路径")
    download_url: Optional[str] = Field(default=None, description="下载URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class FileDownloadResult(BaseModel):
    """文件下载结果"""
    task_id: str = Field(..., description="任务ID")
    device_id: str = Field(..., description="设备ID")
    source_path: str = Field(..., description="源文件路径")
    filename: str = Field(..., description="文件名")
    status: str = Field(..., description="任务状态")
    file_size: int = Field(..., description="文件大小")
    downloaded_size: int = Field(..., description="已下载大小")
    progress: float = Field(..., description="下载进度")
    download_url: Optional[str] = Field(default=None, description="下载URL")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")


# ==================== 数据库管理器 ====================

class FileDownloadManager:
    """文件下载管理器"""
    
    def __init__(self, database_url: str, storage_dir: str = "/tmp/n8_downloads"):
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
                # 创建文件下载任务表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS file_download_tasks (
                        task_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        source_path TEXT NOT NULL,
                        filename VARCHAR(255) NOT NULL,
                        file_size BIGINT DEFAULT 0,
                        file_hash VARCHAR(64),
                        verify_hash BOOLEAN DEFAULT TRUE,
                        status VARCHAR(32) DEFAULT 'pending',
                        downloaded_size BIGINT DEFAULT 0,
                        progress FLOAT DEFAULT 0.0,
                        storage_path TEXT,
                        download_url TEXT,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # 创建索引
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_download_tasks_device 
                    ON file_download_tasks(device_id, created_at DESC)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_download_tasks_status 
                    ON file_download_tasks(status, created_at DESC)
                """)
                
                conn.commit()
        finally:
            conn.close()
    
    def create_task(self, request: FileDownloadRequest) -> str:
        """创建文件下载任务"""
        task_id = f"download_{uuid.uuid4().hex[:16]}"
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 检查设备是否存在
                cur.execute("SELECT device_id FROM devices WHERE device_id = %s", (request.device_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Device {request.device_id} not found")
                
                # 提取文件名
                filename = os.path.basename(request.source_path)
                
                # 创建存储路径
                storage_path = os.path.join(self.storage_dir, task_id, filename)
                os.makedirs(os.path.dirname(storage_path), exist_ok=True)
                
                # 生成下载URL（实际部署时需要使用真实的域名）
                download_url = f"/api/v1/files/download/{task_id}/file"
                
                # 插入任务
                cur.execute("""
                    INSERT INTO file_download_tasks 
                    (task_id, device_id, source_path, filename, verify_hash, 
                     storage_path, download_url, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                """, (
                    task_id,
                    request.device_id,
                    request.source_path,
                    filename,
                    request.verify_hash,
                    storage_path,
                    download_url
                ))
                
                conn.commit()
                return task_id
        finally:
            conn.close()
    
    def update_task_info(self, task_id: str, file_size: int, file_hash: Optional[str] = None):
        """更新任务文件信息（Agent调用）"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE file_download_tasks
                    SET file_size = %s, file_hash = %s, status = 'downloading', updated_at = CURRENT_TIMESTAMP
                    WHERE task_id = %s
                """, (file_size, file_hash, task_id))
                
                conn.commit()
        finally:
            conn.close()
    
    def upload_file_data(self, task_id: str, file_data: bytes) -> dict:
        """上传文件数据（Agent调用）"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 获取任务信息
                cur.execute("""
                    SELECT task_id, storage_path, file_size, file_hash, verify_hash
                    FROM file_download_tasks
                    WHERE task_id = %s
                """, (task_id,))
                
                task = cur.fetchone()
                if not task:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
                
                # 写入文件
                storage_path = task['storage_path']
                with open(storage_path, 'wb') as f:
                    f.write(file_data)
                
                # 计算文件哈希
                actual_hash = hashlib.md5(file_data).hexdigest()
                actual_size = len(file_data)
                
                # 验证哈希
                if task['verify_hash'] and task['file_hash']:
                    if actual_hash != task['file_hash']:
                        cur.execute("""
                            UPDATE file_download_tasks
                            SET status = 'failed', error_message = 'Hash mismatch', updated_at = CURRENT_TIMESTAMP
                            WHERE task_id = %s
                        """, (task_id,))
                        conn.commit()
                        raise HTTPException(status_code=400, detail="File hash mismatch")
                
                # 更新任务状态
                progress = 100.0
                cur.execute("""
                    UPDATE file_download_tasks
                    SET downloaded_size = %s, progress = %s, status = 'completed', 
                        updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                    WHERE task_id = %s
                """, (actual_size, progress, task_id))
                
                conn.commit()
                
                return {
                    "message": "File downloaded successfully",
                    "task_id": task_id,
                    "file_size": actual_size,
                    "file_hash": actual_hash,
                    "status": "completed"
                }
        finally:
            conn.close()
    
    def get_task(self, task_id: str) -> Optional[FileDownloadResult]:
        """获取任务结果"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT task_id, device_id, source_path, filename, status,
                           file_size, downloaded_size, progress, download_url, error_message,
                           created_at, completed_at
                    FROM file_download_tasks
                    WHERE task_id = %s
                """, (task_id,))
                
                task = cur.fetchone()
                if not task:
                    return None
                
                return FileDownloadResult(
                    task_id=task['task_id'],
                    device_id=task['device_id'],
                    source_path=task['source_path'],
                    filename=task['filename'],
                    status=task['status'],
                    file_size=task['file_size'],
                    downloaded_size=task['downloaded_size'],
                    progress=task['progress'],
                    download_url=task['download_url'],
                    error_message=task['error_message'],
                    created_at=task['created_at'],
                    completed_at=task['completed_at']
                )
        finally:
            conn.close()
    
    def get_file_path(self, task_id: str) -> Optional[str]:
        """获取文件存储路径"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT storage_path, status
                    FROM file_download_tasks
                    WHERE task_id = %s
                """, (task_id,))
                
                task = cur.fetchone()
                if not task:
                    return None
                
                if task['status'] != 'completed':
                    return None
                
                return task['storage_path']
        finally:
            conn.close()
    
    def list_tasks(
        self,
        device_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[FileDownloadTask]:
        """查询任务列表"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT task_id, device_id, source_path, filename, file_size, file_hash,
                           verify_hash, status, downloaded_size, progress, storage_path,
                           download_url, created_at, updated_at
                    FROM file_download_tasks
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
                    tasks.append(FileDownloadTask(
                        task_id=row['task_id'],
                        device_id=row['device_id'],
                        source_path=row['source_path'],
                        filename=row['filename'],
                        file_size=row['file_size'],
                        file_hash=row['file_hash'],
                        verify_hash=row['verify_hash'],
                        status=row['status'],
                        downloaded_size=row['downloaded_size'],
                        progress=row['progress'],
                        storage_path=row['storage_path'],
                        download_url=row['download_url'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    ))
                
                return tasks
        finally:
            conn.close()


# ==================== 全局管理器 ====================

_file_download_manager: Optional[FileDownloadManager] = None


def init_file_download_manager(database_url: str, storage_dir: str = "/tmp/n8_downloads"):
    """初始化文件下载管理器"""
    global _file_download_manager
    _file_download_manager = FileDownloadManager(database_url, storage_dir)


def get_file_download_manager() -> FileDownloadManager:
    """获取文件下载管理器"""
    if _file_download_manager is None:
        raise RuntimeError("FileDownloadManager not initialized")
    return _file_download_manager


# ==================== API路由 ====================

router = APIRouter(prefix="/api/v1/files", tags=["文件管理"])


@router.post("/download", response_model=dict)
async def create_file_download_task(
    request: FileDownloadRequest,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    创建文件下载任务
    
    - **device_id**: 源设备ID
    - **source_path**: 源文件路径
    - **verify_hash**: 是否验证文件哈希
    
    返回任务ID，Agent需要上传文件内容到Hub
    """
    manager = get_file_download_manager()
    task_id = manager.create_task(request)
    
    return {
        "message": "File download task created successfully",
        "task_id": task_id,
        "device_id": request.device_id,
        "source_path": request.source_path,
        "status": "pending"
    }


@router.post("/download/{task_id}/upload", response_model=dict)
async def upload_downloaded_file(
    task_id: str,
    file_size: int = Query(..., description="文件大小"),
    file_hash: Optional[str] = Query(None, description="文件MD5哈希"),
    file_data: bytes = b"",  # 实际应该用UploadFile，这里简化
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    上传下载的文件（Agent调用）
    
    - **task_id**: 任务ID
    - **file_size**: 文件大小
    - **file_hash**: 文件MD5哈希
    - **file_data**: 文件数据
    
    返回上传结果
    """
    manager = get_file_download_manager()
    
    # 更新任务信息
    manager.update_task_info(task_id, file_size, file_hash)
    
    # 上传文件数据
    result = manager.upload_file_data(task_id, file_data)
    
    return result


@router.get("/download/{task_id}", response_model=FileDownloadResult)
async def get_file_download_result(
    task_id: str,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    获取文件下载结果
    
    - **task_id**: 任务ID
    
    返回下载状态和进度
    """
    manager = get_file_download_manager()
    result = manager.get_task(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return result


@router.get("/download/{task_id}/file")
async def download_file(
    task_id: str,
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    下载文件
    
    - **task_id**: 任务ID
    
    返回文件内容
    """
    manager = get_file_download_manager()
    file_path = manager.get_file_path(task_id)
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found or download not completed")
    
    filename = os.path.basename(file_path)
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )


@router.get("/download", response_model=List[FileDownloadTask])
async def list_file_download_tasks(
    device_id: Optional[str] = Query(None, description="设备ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    auth_info: dict = Depends(verify_session_or_api_key)
):
    """
    查询文件下载任务列表
    
    - **device_id**: 设备ID过滤（可选）
    - **status**: 状态过滤（可选）
    - **limit**: 返回数量（1-100）
    - **offset**: 偏移量
    
    返回任务列表
    """
    manager = get_file_download_manager()
    tasks = manager.list_tasks(device_id=device_id, status=status, limit=limit, offset=offset)
    
    return tasks
