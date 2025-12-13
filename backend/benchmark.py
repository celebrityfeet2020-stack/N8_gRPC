"""
N8枢纽控制中心 - M3-08 性能基准测试模块
支持CPU、内存、磁盘、网络性能测试
"""

import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import sqlalchemy
from sqlalchemy import text

# 导入认证中间件
from auth_middleware import require_auth


# ============================================================
# Pydantic Models
# ============================================================

class BenchmarkRequest(BaseModel):
    """性能基准测试请求"""
    device_id: str = Field(..., description="设备ID")
    test_types: List[str] = Field(..., description="测试类型列表：cpu/memory/disk/network")
    duration: Optional[int] = Field(30, description="测试持续时间（秒）")


class BenchmarkResponse(BaseModel):
    """性能基准测试响应"""
    benchmark_id: str = Field(..., description="测试ID")
    device_id: str = Field(..., description="设备ID")
    test_types: List[str] = Field(..., description="测试类型列表")
    status: str = Field(..., description="状态：pending/running/completed/failed")
    created_at: str = Field(..., description="创建时间")


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/api/v1/commands", tags=["M3-CommandExecution"])


# ============================================================
# Database Manager
# ============================================================

class BenchmarkManager:
    """性能基准测试管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = sqlalchemy.create_engine(database_url)
    
    async def create_benchmark(
        self,
        device_id: str,
        test_types: List[str],
        duration: int = 30
    ) -> dict:
        """创建性能基准测试"""
        # 验证测试类型
        valid_types = ['cpu', 'memory', 'disk', 'network']
        for test_type in test_types:
            if test_type not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid test type: {test_type}. Must be one of: {', '.join(valid_types)}"
                )
        
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
        
        # 生成测试ID
        benchmark_id = f"bench-{uuid.uuid4().hex[:16]}"
        created_at = datetime.now()
        
        # 创建性能基准测试任务
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO benchmark_tasks 
                    (benchmark_id, device_id, test_types, duration, status, created_at)
                    VALUES (:benchmark_id, :device_id, :test_types, :duration, :status, :created_at)
                """),
                {
                    "benchmark_id": benchmark_id,
                    "device_id": device_id,
                    "test_types": sqlalchemy.dialects.postgresql.ARRAY(sqlalchemy.String)(test_types),
                    "duration": duration,
                    "status": "pending",
                    "created_at": created_at
                }
            )
            conn.commit()
        
        return {
            "benchmark_id": benchmark_id,
            "device_id": device_id,
            "test_types": test_types,
            "status": "pending",
            "message": f"Benchmark test scheduled. Agent will execute it.",
            "created_at": created_at.isoformat()
        }


# 全局管理器实例
_benchmark_manager: Optional[BenchmarkManager] = None


def get_benchmark_manager() -> BenchmarkManager:
    """获取性能基准测试管理器实例"""
    if _benchmark_manager is None:
        raise RuntimeError("BenchmarkManager not initialized")
    return _benchmark_manager


def init_benchmark_manager(database_url: str):
    """初始化性能基准测试管理器"""
    global _benchmark_manager
    _benchmark_manager = BenchmarkManager(database_url)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/benchmark", response_model=BenchmarkResponse)
async def start_benchmark(
    request: BenchmarkRequest,
    auth_info: dict = Depends(require_auth)
):
    """
    启动性能基准测试
    
    **权限**: command:execute
    
    **测试类型**:
    - **cpu**: CPU性能测试
      - 单核性能
      - 多核性能
      - 浮点运算性能
      - 整数运算性能
    
    - **memory**: 内存性能测试
      - 读取速度
      - 写入速度
      - 随机访问速度
      - 顺序访问速度
    
    - **disk**: 磁盘性能测试
      - 顺序读取速度
      - 顺序写入速度
      - 随机读取速度（4K）
      - 随机写入速度（4K）
      - IOPS
    
    - **network**: 网络性能测试
      - 下载速度
      - 上传速度
      - 延迟
      - 丢包率
    
    **参数说明**:
    - test_types: 可以同时测试多个类型
    - duration: 每个测试的持续时间（秒）
    
    **注意事项**:
    - 测试期间会占用系统资源
    - 磁盘测试会产生临时文件
    - 网络测试需要外网连接
    """
    manager = get_benchmark_manager()
    
    result = await manager.create_benchmark(
        device_id=request.device_id,
        test_types=request.test_types,
        duration=request.duration or 30
    )
    
    return BenchmarkResponse(**result)


@router.get("/benchmark/{benchmark_id}", response_model=dict)
async def get_benchmark_result(
    benchmark_id: str,
    auth_info: dict = Depends(require_auth)
):
    """
    获取性能基准测试结果
    
    **权限**: metrics:read
    
    **返回数据**:
    - 测试状态
    - 测试结果（完成后）
    - 性能分数
    - 详细指标
    """
    manager = get_benchmark_manager()
    
    with manager.engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT benchmark_id, device_id, test_types, duration, status, 
                       result_data, created_at, completed_at
                FROM benchmark_tasks
                WHERE benchmark_id = :benchmark_id
            """),
            {"benchmark_id": benchmark_id}
        )
        benchmark = result.fetchone()
        
        if not benchmark:
            raise HTTPException(status_code=404, detail=f"Benchmark not found: {benchmark_id}")
        
        return {
            "benchmark_id": benchmark[0],
            "device_id": benchmark[1],
            "test_types": benchmark[2],
            "duration": benchmark[3],
            "status": benchmark[4],
            "result_data": benchmark[5],
            "created_at": benchmark[6].isoformat(),
            "completed_at": benchmark[7].isoformat() if benchmark[7] else None
        }
