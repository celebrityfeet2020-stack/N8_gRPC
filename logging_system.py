"""
M7日志系统模块
整合5个子模块：命令执行日志、Agent日志上传、系统事件日志、日志查询API、日志分析引擎
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor
import json

from auth_middleware import require_auth


# ==================== 数据模型 ====================

class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(str, Enum):
    """日志类别"""
    COMMAND = "command"          # 命令执行日志
    AGENT = "agent"              # Agent日志
    SYSTEM = "system"            # 系统事件日志
    API = "api"                  # API调用日志
    WORKFLOW = "workflow"        # 工作流日志


# M7-01: 命令执行日志
class CommandLogCreate(BaseModel):
    """创建命令执行日志"""
    device_id: str
    command: str
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    execution_time_ms: Optional[int] = None


# M7-02: Agent日志上传
class AgentLogUpload(BaseModel):
    """Agent日志上传"""
    device_id: str
    level: LogLevel
    message: str
    module: Optional[str] = None
    function: Optional[str] = None
    line_number: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None


# M7-03: 系统事件日志
class SystemEventLog(BaseModel):
    """系统事件日志"""
    device_id: str
    event_type: str  # device_online, device_offline, task_created, task_completed, etc.
    event_data: Optional[Dict[str, Any]] = None
    severity: LogLevel = LogLevel.INFO


# M7-04: 日志查询请求
class LogQueryRequest(BaseModel):
    """日志查询请求"""
    device_id: Optional[str] = None
    category: Optional[LogCategory] = None
    level: Optional[LogLevel] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    keyword: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


# M7-05: 日志分析结果
class LogAnalysisResult(BaseModel):
    """日志分析结果"""
    total_logs: int
    error_count: int
    warning_count: int
    top_errors: List[Dict[str, Any]]
    device_stats: List[Dict[str, Any]]
    time_distribution: List[Dict[str, Any]]


# ==================== 路由 ====================

router = APIRouter(prefix="/api/v1/logs", tags=["M7-Logging"])


# ==================== 全局变量 ====================

db_url = None


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(db_url)


# ==================== M7-01: 命令执行日志 ====================

@router.post("/command")
async def create_command_log(
    log: CommandLogCreate,
    auth: dict = Depends(require_auth)
):
    """
    创建命令执行日志
    记录设备上执行的命令及其结果
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO command_logs_m7 
                (device_id, command, exit_code, stdout, stderr, execution_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING log_id, created_at
            """, (
                log.device_id,
                log.command,
                log.exit_code,
                log.stdout,
                log.stderr,
                log.execution_time_ms
            ))
            result = cur.fetchone()
            conn.commit()
            
            return {
                "log_id": result[0],
                "created_at": result[1].isoformat(),
                "message": "命令执行日志已创建"
            }
    finally:
        conn.close()


# ==================== M7-02: Agent日志上传 ====================

@router.post("/agent")
async def upload_agent_log(
    log: AgentLogUpload,
    auth: dict = Depends(require_auth)
):
    """
    Agent日志上传
    Agent定期上传运行日志到Hub
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO agent_logs 
                (device_id, level, message, module, function, line_number, extra_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING log_id, created_at
            """, (
                log.device_id,
                log.level.value,
                log.message,
                log.module,
                log.function,
                log.line_number,
                json.dumps(log.extra_data) if log.extra_data else None
            ))
            result = cur.fetchone()
            conn.commit()
            
            return {
                "log_id": result[0],
                "created_at": result[1].isoformat(),
                "message": "Agent日志已上传"
            }
    finally:
        conn.close()


@router.post("/agent/batch")
async def upload_agent_logs_batch(
    logs: List[AgentLogUpload],
    auth: dict = Depends(require_auth)
):
    """
    批量上传Agent日志
    提高上传效率
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for log in logs:
                cur.execute("""
                    INSERT INTO agent_logs 
                    (device_id, level, message, module, function, line_number, extra_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    log.device_id,
                    log.level.value,
                    log.message,
                    log.module,
                    log.function,
                    log.line_number,
                    json.dumps(log.extra_data) if log.extra_data else None
                ))
            conn.commit()
            
            return {
                "count": len(logs),
                "message": f"已批量上传{len(logs)}条Agent日志"
            }
    finally:
        conn.close()


# ==================== M7-03: 系统事件日志 ====================

@router.post("/system-event")
async def create_system_event_log(
    log: SystemEventLog,
    auth: dict = Depends(require_auth)
):
    """
    创建系统事件日志
    记录系统级别的重要事件
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO system_event_logs 
                (device_id, event_type, event_data, severity)
                VALUES (%s, %s, %s, %s)
                RETURNING log_id, created_at
            """, (
                log.device_id,
                log.event_type,
                json.dumps(log.event_data) if log.event_data else None,
                log.severity.value
            ))
            result = cur.fetchone()
            conn.commit()
            
            return {
                "log_id": result[0],
                "created_at": result[1].isoformat(),
                "message": "系统事件日志已创建"
            }
    finally:
        conn.close()


# ==================== M7-04: 日志查询API ====================

@router.post("/query")
async def query_logs(
    query: LogQueryRequest,
    auth: dict = Depends(require_auth)
):
    """
    日志查询API
    支持多条件组合查询
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 构建查询条件
            conditions = []
            params = []
            
            if query.device_id:
                conditions.append("device_id = %s")
                params.append(query.device_id)
            
            if query.level:
                conditions.append("level = %s")
                params.append(query.level.value)
            
            if query.start_time:
                conditions.append("created_at >= %s")
                params.append(query.start_time)
            
            if query.end_time:
                conditions.append("created_at <= %s")
                params.append(query.end_time)
            
            if query.keyword:
                conditions.append("message ILIKE %s")
                params.append(f"%{query.keyword}%")
            
            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            
            # 根据类别选择表
            if query.category == LogCategory.COMMAND:
                table = "command_logs_m7"
            elif query.category == LogCategory.AGENT:
                table = "agent_logs"
            elif query.category == LogCategory.SYSTEM:
                table = "system_event_logs"
            else:
                # 联合查询所有表
                sql = f"""
                    (SELECT log_id, device_id, 'command' as category, 
                            'info' as level, command as message, created_at
                     FROM command_logs_m7 WHERE {where_clause})
                    UNION ALL
                    (SELECT log_id, device_id, 'agent' as category, 
                            level, message, created_at
                     FROM agent_logs WHERE {where_clause})
                    UNION ALL
                    (SELECT log_id, device_id, 'system' as category, 
                            severity as level, event_type as message, created_at
                     FROM system_event_logs WHERE {where_clause})
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([query.limit, query.offset])
                cur.execute(sql, params * 3)  # 3个子查询都需要参数
                logs = cur.fetchall()
                
                return {
                    "logs": logs,
                    "count": len(logs),
                    "limit": query.limit,
                    "offset": query.offset
                }
            
            # 单表查询
            sql = f"""
                SELECT * FROM {table}
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([query.limit, query.offset])
            cur.execute(sql, params)
            logs = cur.fetchall()
            
            return {
                "logs": logs,
                "count": len(logs),
                "limit": query.limit,
                "offset": query.offset
            }
    finally:
        conn.close()


@router.get("/device/{device_id}")
async def get_device_logs(
    device_id: str,
    level: Optional[LogLevel] = None,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=1000),
    auth: dict = Depends(require_auth)
):
    """
    获取指定设备的日志
    默认返回最近24小时的日志
    """
    start_time = datetime.now() - timedelta(hours=hours)
    
    query = LogQueryRequest(
        device_id=device_id,
        level=level,
        start_time=start_time,
        limit=limit
    )
    
    return await query_logs(query, auth)


# ==================== M7-05: 日志分析引擎 ====================

@router.get("/analysis")
async def analyze_logs(
    device_id: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=168),
    auth: dict = Depends(require_auth)
):
    """
    日志分析引擎
    统计分析日志数据，提供洞察
    """
    start_time = datetime.now() - timedelta(hours=hours)
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 构建设备过滤条件
            device_filter = "device_id = %s AND " if device_id else ""
            device_param = [device_id] if device_id else []
            
            # 1. 总日志数和错误统计
            cur.execute(f"""
                SELECT 
                    COUNT(*) as total_logs,
                    SUM(CASE WHEN level = 'error' THEN 1 ELSE 0 END) as error_count,
                    SUM(CASE WHEN level = 'warning' THEN 1 ELSE 0 END) as warning_count
                FROM agent_logs
                WHERE {device_filter}created_at >= %s
            """, device_param + [start_time])
            stats = cur.fetchone()
            
            # 2. Top错误
            cur.execute(f"""
                SELECT message, COUNT(*) as count
                FROM agent_logs
                WHERE {device_filter}created_at >= %s AND level = 'error'
                GROUP BY message
                ORDER BY count DESC
                LIMIT 10
            """, device_param + [start_time])
            top_errors = cur.fetchall()
            
            # 3. 设备统计
            cur.execute(f"""
                SELECT 
                    device_id,
                    COUNT(*) as log_count,
                    SUM(CASE WHEN level = 'error' THEN 1 ELSE 0 END) as error_count
                FROM agent_logs
                WHERE {device_filter}created_at >= %s
                GROUP BY device_id
                ORDER BY log_count DESC
                LIMIT 10
            """, device_param + [start_time])
            device_stats = cur.fetchall()
            
            # 4. 时间分布（按小时）
            cur.execute(f"""
                SELECT 
                    DATE_TRUNC('hour', created_at) as hour,
                    COUNT(*) as count
                FROM agent_logs
                WHERE {device_filter}created_at >= %s
                GROUP BY hour
                ORDER BY hour
            """, device_param + [start_time])
            time_distribution = cur.fetchall()
            
            return {
                "total_logs": stats['total_logs'],
                "error_count": stats['error_count'],
                "warning_count": stats['warning_count'],
                "top_errors": top_errors,
                "device_stats": device_stats,
                "time_distribution": time_distribution,
                "analysis_period_hours": hours
            }
    finally:
        conn.close()


@router.get("/analysis/errors")
async def analyze_errors(
    device_id: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=168),
    auth: dict = Depends(require_auth)
):
    """
    错误日志分析
    专注于错误日志的深度分析
    """
    start_time = datetime.now() - timedelta(hours=hours)
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            device_filter = "device_id = %s AND " if device_id else ""
            device_param = [device_id] if device_id else []
            
            # 错误分类统计
            cur.execute(f"""
                SELECT 
                    module,
                    COUNT(*) as count,
                    array_agg(DISTINCT message) as messages
                FROM agent_logs
                WHERE {device_filter}created_at >= %s AND level = 'error'
                GROUP BY module
                ORDER BY count DESC
            """, device_param + [start_time])
            error_by_module = cur.fetchall()
            
            # 最近错误
            cur.execute(f"""
                SELECT *
                FROM agent_logs
                WHERE {device_filter}created_at >= %s AND level = 'error'
                ORDER BY created_at DESC
                LIMIT 50
            """, device_param + [start_time])
            recent_errors = cur.fetchall()
            
            return {
                "error_by_module": error_by_module,
                "recent_errors": recent_errors,
                "analysis_period_hours": hours
            }
    finally:
        conn.close()


# ==================== 初始化 ====================

def init_logging_manager(database_url: str):
    """初始化日志管理器"""
    global db_url
    db_url = database_url
    print("✅ 日志系统管理器已初始化")
