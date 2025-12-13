"""
M8工作流编排模块
整合4个子模块：Temporal集成、设备备份工作流、批量命令工作流、健康检查工作流
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import uuid

from auth_middleware import require_auth


# ==================== 数据模型 ====================

class WorkflowStatus(str, Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowType(str, Enum):
    """工作流类型"""
    DEVICE_BACKUP = "device_backup"
    BATCH_COMMAND = "batch_command"
    HEALTH_CHECK = "health_check"
    CUSTOM = "custom"


class StepStatus(str, Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# M8-02: 设备备份工作流
class DeviceBackupWorkflow(BaseModel):
    """设备备份工作流"""
    device_id: str
    backup_type: str = "full"  # full, incremental
    backup_paths: List[str]
    destination: str
    compress: bool = True
    encrypt: bool = False


# M8-03: 批量命令工作流
class BatchCommandWorkflow(BaseModel):
    """批量命令工作流"""
    device_ids: List[str]
    commands: List[str]
    parallel: bool = False
    stop_on_error: bool = True
    timeout_seconds: int = 300


# M8-04: 健康检查工作流
class HealthCheckWorkflow(BaseModel):
    """健康检查工作流"""
    device_ids: Optional[List[str]] = None  # None表示所有设备
    check_items: List[str] = ["cpu", "memory", "disk", "network"]
    thresholds: Optional[Dict[str, float]] = None


# 通用工作流创建
class WorkflowCreate(BaseModel):
    """创建工作流"""
    name: str
    workflow_type: WorkflowType
    config: Dict[str, Any]
    schedule: Optional[str] = None  # Cron表达式


# 工作流步骤
class WorkflowStepCreate(BaseModel):
    """创建工作流步骤"""
    workflow_id: str
    step_name: str
    step_order: int
    action: str
    parameters: Dict[str, Any]
    depends_on: Optional[List[str]] = None


# ==================== 路由 ====================

router = APIRouter(prefix="/api/v1/workflows", tags=["M8-Workflow"])


# ==================== 全局变量 ====================

db_url = None


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(db_url)


# ==================== M8-01: Temporal集成（基础工作流管理）====================

@router.post("")
async def create_workflow(
    workflow: WorkflowCreate,
    auth: dict = Depends(require_auth)
):
    """
    创建工作流
    支持多种工作流类型
    """
    workflow_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO workflows 
                (workflow_id, name, workflow_type, config, schedule, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING created_at
            """, (
                workflow_id,
                workflow.name,
                workflow.workflow_type.value,
                json.dumps(workflow.config),
                workflow.schedule,
                WorkflowStatus.PENDING.value
            ))
            result = cur.fetchone()
            conn.commit()
            
            return {
                "workflow_id": workflow_id,
                "name": workflow.name,
                "status": WorkflowStatus.PENDING.value,
                "created_at": result[0].isoformat(),
                "message": "工作流已创建"
            }
    finally:
        conn.close()


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    auth: dict = Depends(require_auth)
):
    """
    获取工作流详情
    包括所有步骤和执行状态
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 获取工作流信息
            cur.execute("""
                SELECT * FROM workflows WHERE workflow_id = %s
            """, (workflow_id,))
            workflow = cur.fetchone()
            
            if not workflow:
                raise HTTPException(status_code=404, detail="工作流不存在")
            
            # 获取工作流步骤
            cur.execute("""
                SELECT * FROM workflow_steps 
                WHERE workflow_id = %s 
                ORDER BY step_order
            """, (workflow_id,))
            steps = cur.fetchall()
            
            # 获取执行历史
            cur.execute("""
                SELECT * FROM workflow_executions 
                WHERE workflow_id = %s 
                ORDER BY started_at DESC 
                LIMIT 10
            """, (workflow_id,))
            executions = cur.fetchall()
            
            return {
                "workflow": workflow,
                "steps": steps,
                "executions": executions
            }
    finally:
        conn.close()


@router.get("")
async def list_workflows(
    workflow_type: Optional[WorkflowType] = None,
    status: Optional[WorkflowStatus] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: dict = Depends(require_auth)
):
    """
    列出所有工作流
    支持按类型和状态过滤
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params = []
            
            if workflow_type:
                conditions.append("workflow_type = %s")
                params.append(workflow_type.value)
            
            if status:
                conditions.append("status = %s")
                params.append(status.value)
            
            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            
            cur.execute(f"""
                SELECT * FROM workflows
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params + [limit, offset])
            workflows = cur.fetchall()
            
            return {
                "workflows": workflows,
                "count": len(workflows),
                "limit": limit,
                "offset": offset
            }
    finally:
        conn.close()


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    auth: dict = Depends(require_auth)
):
    """
    执行工作流
    异步执行，立即返回execution_id
    """
    execution_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 检查工作流是否存在
            cur.execute("""
                SELECT workflow_type, config FROM workflows WHERE workflow_id = %s
            """, (workflow_id,))
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="工作流不存在")
            
            workflow_type, config = result
            
            # 创建执行记录
            cur.execute("""
                INSERT INTO workflow_executions 
                (execution_id, workflow_id, status, started_at)
                VALUES (%s, %s, %s, %s)
            """, (
                execution_id,
                workflow_id,
                WorkflowStatus.RUNNING.value,
                datetime.now()
            ))
            
            # 更新工作流状态
            cur.execute("""
                UPDATE workflows 
                SET status = %s, last_execution_at = %s
                WHERE workflow_id = %s
            """, (WorkflowStatus.RUNNING.value, datetime.now(), workflow_id))
            
            conn.commit()
            
            # 后台执行工作流（这里简化处理，实际应该调用Temporal）
            # background_tasks.add_task(execute_workflow_steps, execution_id, workflow_type, config)
            
            return {
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "status": WorkflowStatus.RUNNING.value,
                "message": "工作流已开始执行"
            }
    finally:
        conn.close()


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(
    workflow_id: str,
    auth: dict = Depends(require_auth)
):
    """
    取消工作流执行
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE workflows 
                SET status = %s 
                WHERE workflow_id = %s AND status = %s
                RETURNING workflow_id
            """, (WorkflowStatus.CANCELLED.value, workflow_id, WorkflowStatus.RUNNING.value))
            
            result = cur.fetchone()
            conn.commit()
            
            if not result:
                raise HTTPException(status_code=400, detail="工作流未在运行中或不存在")
            
            return {
                "workflow_id": workflow_id,
                "status": WorkflowStatus.CANCELLED.value,
                "message": "工作流已取消"
            }
    finally:
        conn.close()


# ==================== M8-02: 设备备份工作流 ====================

@router.post("/backup")
async def create_backup_workflow(
    backup: DeviceBackupWorkflow,
    auth: dict = Depends(require_auth)
):
    """
    创建设备备份工作流
    自动备份设备数据
    """
    workflow = WorkflowCreate(
        name=f"设备备份 - {backup.device_id}",
        workflow_type=WorkflowType.DEVICE_BACKUP,
        config={
            "device_id": backup.device_id,
            "backup_type": backup.backup_type,
            "backup_paths": backup.backup_paths,
            "destination": backup.destination,
            "compress": backup.compress,
            "encrypt": backup.encrypt
        }
    )
    
    return await create_workflow(workflow, auth)


@router.get("/backup/{device_id}/history")
async def get_backup_history(
    device_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    auth: dict = Depends(require_auth)
):
    """
    获取设备备份历史
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT w.*, we.execution_id, we.status as execution_status, 
                       we.started_at, we.completed_at, we.result
                FROM workflows w
                LEFT JOIN workflow_executions we ON w.workflow_id = we.workflow_id
                WHERE w.workflow_type = %s 
                  AND w.config->>'device_id' = %s
                ORDER BY we.started_at DESC
                LIMIT %s
            """, (WorkflowType.DEVICE_BACKUP.value, device_id, limit))
            
            backups = cur.fetchall()
            
            return {
                "device_id": device_id,
                "backups": backups,
                "count": len(backups)
            }
    finally:
        conn.close()


# ==================== M8-03: 批量命令工作流 ====================

@router.post("/batch-command")
async def create_batch_command_workflow(
    batch: BatchCommandWorkflow,
    auth: dict = Depends(require_auth)
):
    """
    创建批量命令工作流
    在多个设备上执行相同命令
    """
    workflow = WorkflowCreate(
        name=f"批量命令 - {len(batch.device_ids)}台设备",
        workflow_type=WorkflowType.BATCH_COMMAND,
        config={
            "device_ids": batch.device_ids,
            "commands": batch.commands,
            "parallel": batch.parallel,
            "stop_on_error": batch.stop_on_error,
            "timeout_seconds": batch.timeout_seconds
        }
    )
    
    return await create_workflow(workflow, auth)


@router.get("/batch-command/{workflow_id}/progress")
async def get_batch_command_progress(
    workflow_id: str,
    auth: dict = Depends(require_auth)
):
    """
    获取批量命令执行进度
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 获取工作流配置
            cur.execute("""
                SELECT config FROM workflows WHERE workflow_id = %s
            """, (workflow_id,))
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="工作流不存在")
            
            config = result['config']
            device_ids = config.get('device_ids', [])
            
            # 获取执行进度
            cur.execute("""
                SELECT 
                    COUNT(*) as total_steps,
                    SUM(CASE WHEN status = %s THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = %s THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = %s THEN 1 ELSE 0 END) as running
                FROM workflow_steps
                WHERE workflow_id = %s
            """, (StepStatus.COMPLETED.value, StepStatus.FAILED.value, 
                  StepStatus.RUNNING.value, workflow_id))
            
            progress = cur.fetchone()
            
            return {
                "workflow_id": workflow_id,
                "total_devices": len(device_ids),
                "total_steps": progress['total_steps'],
                "completed": progress['completed'],
                "failed": progress['failed'],
                "running": progress['running'],
                "progress_percent": (progress['completed'] / progress['total_steps'] * 100) if progress['total_steps'] > 0 else 0
            }
    finally:
        conn.close()


# ==================== M8-04: 健康检查工作流 ====================

@router.post("/health-check")
async def create_health_check_workflow(
    health_check: HealthCheckWorkflow,
    auth: dict = Depends(require_auth)
):
    """
    创建健康检查工作流
    定期检查设备健康状态
    """
    workflow = WorkflowCreate(
        name=f"健康检查 - {len(health_check.device_ids or [])}台设备",
        workflow_type=WorkflowType.HEALTH_CHECK,
        config={
            "device_ids": health_check.device_ids,
            "check_items": health_check.check_items,
            "thresholds": health_check.thresholds or {
                "cpu": 80.0,
                "memory": 85.0,
                "disk": 90.0
            }
        },
        schedule="0 */1 * * *"  # 每小时执行一次
    )
    
    return await create_workflow(workflow, auth)


@router.get("/health-check/{workflow_id}/report")
async def get_health_check_report(
    workflow_id: str,
    auth: dict = Depends(require_auth)
):
    """
    获取健康检查报告
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 获取最新执行结果
            cur.execute("""
                SELECT * FROM workflow_executions
                WHERE workflow_id = %s
                ORDER BY started_at DESC
                LIMIT 1
            """, (workflow_id,))
            
            execution = cur.fetchone()
            
            if not execution:
                raise HTTPException(status_code=404, detail="未找到执行记录")
            
            # 解析结果
            result = execution.get('result', {})
            
            return {
                "workflow_id": workflow_id,
                "execution_id": execution['execution_id'],
                "status": execution['status'],
                "started_at": execution['started_at'].isoformat() if execution['started_at'] else None,
                "completed_at": execution['completed_at'].isoformat() if execution['completed_at'] else None,
                "report": result,
                "healthy_devices": result.get('healthy_devices', []),
                "unhealthy_devices": result.get('unhealthy_devices', []),
                "warnings": result.get('warnings', [])
            }
    finally:
        conn.close()


@router.get("/health-check/summary")
async def get_health_check_summary(
    hours: int = Query(default=24, ge=1, le=168),
    auth: dict = Depends(require_auth)
):
    """
    获取健康检查汇总
    最近N小时的健康检查统计
    """
    start_time = datetime.now() - timedelta(hours=hours)
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT we.workflow_id) as total_checks,
                    SUM(CASE WHEN we.status = %s THEN 1 ELSE 0 END) as successful_checks,
                    SUM(CASE WHEN we.status = %s THEN 1 ELSE 0 END) as failed_checks
                FROM workflow_executions we
                JOIN workflows w ON we.workflow_id = w.workflow_id
                WHERE w.workflow_type = %s AND we.started_at >= %s
            """, (WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value,
                  WorkflowType.HEALTH_CHECK.value, start_time))
            
            summary = cur.fetchone()
            
            return {
                "period_hours": hours,
                "total_checks": summary['total_checks'],
                "successful_checks": summary['successful_checks'],
                "failed_checks": summary['failed_checks'],
                "success_rate": (summary['successful_checks'] / summary['total_checks'] * 100) if summary['total_checks'] > 0 else 0
            }
    finally:
        conn.close()


# ==================== 工作流步骤管理 ====================

@router.post("/{workflow_id}/steps")
async def add_workflow_step(
    workflow_id: str,
    step: WorkflowStepCreate,
    auth: dict = Depends(require_auth)
):
    """
    添加工作流步骤
    """
    step_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO workflow_steps 
                (step_id, workflow_id, step_name, step_order, action, parameters, depends_on, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING created_at
            """, (
                step_id,
                workflow_id,
                step.step_name,
                step.step_order,
                step.action,
                json.dumps(step.parameters),
                json.dumps(step.depends_on) if step.depends_on else None,
                StepStatus.PENDING.value
            ))
            result = cur.fetchone()
            conn.commit()
            
            return {
                "step_id": step_id,
                "workflow_id": workflow_id,
                "step_name": step.step_name,
                "created_at": result[0].isoformat(),
                "message": "工作流步骤已添加"
            }
    finally:
        conn.close()


# ==================== 初始化 ====================

def init_workflow_manager(database_url: str):
    """初始化工作流管理器"""
    global db_url
    db_url = database_url
    print("✅ 工作流编排管理器已初始化")
