"""
N8枢纽控制中心 - M3-01 Shell命令执行模块
支持Windows、macOS、Linux，支持超时控制
"""

import os
import uuid
import asyncio
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import sqlalchemy
from sqlalchemy import text

# 导入认证中间件
from auth_middleware import require_auth


# ============================================================
# Pydantic Models
# ============================================================

class CommandExecuteRequest(BaseModel):
    """命令执行请求"""
    device_id: str = Field(..., description="设备ID")
    command: str = Field(..., description="要执行的Shell命令")
    timeout: Optional[int] = Field(30, description="超时时间（秒），默认30秒")
    working_dir: Optional[str] = Field(None, description="工作目录")
    env_vars: Optional[Dict[str, str]] = Field(None, description="环境变量")


class CommandExecuteResponse(BaseModel):
    """命令执行响应"""
    execution_id: str = Field(..., description="执行ID")
    device_id: str = Field(..., description="设备ID")
    command: str = Field(..., description="执行的命令")
    status: str = Field(..., description="执行状态: pending/running/completed/failed/timeout")
    exit_code: Optional[int] = Field(None, description="退出码")
    stdout: Optional[str] = Field(None, description="标准输出")
    stderr: Optional[str] = Field(None, description="标准错误")
    execution_time: Optional[float] = Field(None, description="执行时间（秒）")
    started_at: Optional[str] = Field(None, description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/api/v1/commands", tags=["M3-CommandExecution"])


# ============================================================
# Database Manager
# ============================================================

class CommandExecuteManager:
    """命令执行管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = sqlalchemy.create_engine(database_url)
    
    async def execute_command(
        self,
        device_id: str,
        command: str,
        timeout: int = 30,
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        执行Shell命令
        
        Args:
            device_id: 设备ID
            command: 要执行的命令
            timeout: 超时时间（秒）
            working_dir: 工作目录
            env_vars: 环境变量
        
        Returns:
            执行结果字典
        """
        # 生成执行ID
        execution_id = f"exec-{uuid.uuid4().hex[:16]}"
        
        # 检查设备是否存在
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT device_id, status FROM devices WHERE device_id = :device_id"),
                {"device_id": device_id}
            )
            device = result.fetchone()
            
            if not device:
                raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
            
            if device[1] != 'online':
                raise HTTPException(
                    status_code=400,
                    detail=f"Device is not online: {device_id} (status: {device[1]})"
                )
        
        # 记录命令执行开始
        started_at = datetime.now()
        
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO command_executions 
                    (execution_id, device_id, command, status, started_at, created_at)
                    VALUES (:execution_id, :device_id, :command, :status, :started_at, :created_at)
                """),
                {
                    "execution_id": execution_id,
                    "device_id": device_id,
                    "command": command,
                    "status": "running",
                    "started_at": started_at,
                    "created_at": datetime.now()
                }
            )
            conn.commit()
        
        # 准备环境变量
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        
        # 执行命令
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env
            )
            
            # 等待命令完成（带超时）
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                exit_code = process.returncode
                status = "completed" if exit_code == 0 else "failed"
                
            except asyncio.TimeoutError:
                # 超时，终止进程
                process.kill()
                await process.wait()
                stdout = b""
                stderr = b"Command execution timeout"
                exit_code = -1
                status = "timeout"
        
        except Exception as e:
            stdout = b""
            stderr = str(e).encode()
            exit_code = -1
            status = "failed"
        
        # 计算执行时间
        completed_at = datetime.now()
        execution_time = (completed_at - started_at).total_seconds()
        
        # 更新数据库
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE command_executions 
                    SET status = :status,
                        exit_code = :exit_code,
                        stdout = :stdout,
                        stderr = :stderr,
                        execution_time = :execution_time,
                        completed_at = :completed_at,
                        updated_at = :updated_at
                    WHERE execution_id = :execution_id
                """),
                {
                    "execution_id": execution_id,
                    "status": status,
                    "exit_code": exit_code,
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "execution_time": execution_time,
                    "completed_at": completed_at,
                    "updated_at": datetime.now()
                }
            )
            conn.commit()
        
        return {
            "execution_id": execution_id,
            "device_id": device_id,
            "command": command,
            "status": status,
            "exit_code": exit_code,
            "stdout": stdout.decode('utf-8', errors='replace'),
            "stderr": stderr.decode('utf-8', errors='replace'),
            "execution_time": execution_time,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat()
        }
    
    async def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取命令执行结果
        
        Args:
            execution_id: 执行ID
        
        Returns:
            执行结果字典，如果不存在则返回None
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT execution_id, device_id, command, status, exit_code,
                           stdout, stderr, execution_time, started_at, completed_at
                    FROM command_executions
                    WHERE execution_id = :execution_id
                """),
                {"execution_id": execution_id}
            )
            row = result.fetchone()
            
            if not row:
                return None
            
            return {
                "execution_id": row[0],
                "device_id": row[1],
                "command": row[2],
                "status": row[3],
                "exit_code": row[4],
                "stdout": row[5],
                "stderr": row[6],
                "execution_time": row[7],
                "started_at": row[8].isoformat() if row[8] else None,
                "completed_at": row[9].isoformat() if row[9] else None
            }


# 全局管理器实例
_command_manager: Optional[CommandExecuteManager] = None


def get_command_manager() -> CommandExecuteManager:
    """获取命令执行管理器实例"""
    if _command_manager is None:
        raise RuntimeError("CommandExecuteManager not initialized")
    return _command_manager


def init_command_manager(database_url: str):
    """初始化命令执行管理器"""
    global _command_manager
    _command_manager = CommandExecuteManager(database_url)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/execute", response_model=CommandExecuteResponse)
async def execute_command(
    request: CommandExecuteRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    执行Shell命令
    
    **权限**: command:execute
    
    **功能**:
    - 支持Windows、macOS、Linux
    - 支持超时控制
    - 支持自定义工作目录
    - 支持自定义环境变量
    - 异步执行，立即返回执行ID
    
    **注意事项**:
    - 命令执行有超时限制（默认30秒）
    - 设备必须在线才能执行命令
    - 命令执行结果会保存到数据库
    """
    manager = get_command_manager()
    
    result = await manager.execute_command(
        device_id=request.device_id,
        command=request.command,
        timeout=request.timeout or 30,
        working_dir=request.working_dir,
        env_vars=request.env_vars
    )
    
    return CommandExecuteResponse(**result)


@router.get("/executions/{execution_id}", response_model=CommandExecuteResponse)
async def get_execution(
    execution_id: str,
    auth_info: dict = Depends(require_auth)
):
    """
    获取命令执行结果
    
    **权限**: command:execute
    
    **功能**:
    - 查询命令执行状态
    - 获取命令输出（stdout/stderr）
    - 获取执行时间和退出码
    """
    manager = get_command_manager()
    
    result = await manager.get_execution(execution_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")
    
    return CommandExecuteResponse(**result)
