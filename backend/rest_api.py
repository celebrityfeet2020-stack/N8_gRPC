"""
N8 gRPC Control Center - REST API
提供给Web前端调用的HTTP API
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
import json

from sqlalchemy.orm import Session
from models import Device, Command, AuditLog
from grpc_server import DatabaseManager, ControlCenterConfig


# ============================================
# FastAPI应用
# ============================================

app = FastAPI(
    title="N8 Control Center API",
    description="设备控制中心REST API",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局配置和数据库管理器
config = ControlCenterConfig()
db_manager = DatabaseManager(config.database_url)


# ============================================
# 依赖注入
# ============================================

def get_db():
    """获取数据库会话"""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


# ============================================
# Pydantic模型
# ============================================

class DeviceResponse(BaseModel):
    """设备响应模型"""
    id: int
    device_id: str
    hostname: str
    os_type: str
    os_version: Optional[str]
    agent_version: Optional[str]
    status: str
    last_seen_at: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime: int
    running_services: List[str]
    metadata: dict
    created_at: datetime
    
    class Config:
        from_attributes = True


class CommandRequest(BaseModel):
    """命令请求模型"""
    command_type: str  # exec/restart
    payload: dict
    timeout: int = 300


class CommandResponse(BaseModel):
    """命令响应模型"""
    id: int
    command_id: str
    device_id: str
    command_type: str
    payload: str
    status: str
    success: Optional[bool]
    stdout: Optional[str]
    stderr: Optional[str]
    exit_code: Optional[int]
    executed_at: Optional[datetime]
    duration_ms: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================
# API路由
# ============================================

@app.get("/")
def root():
    """根路径"""
    return {
        "name": "N8 Control Center API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/devices", response_model=List[DeviceResponse])
def list_devices(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取设备列表"""
    query = db.query(Device)
    
    if status:
        query = query.filter(Device.status == status)
    
    devices = query.order_by(Device.last_seen_at.desc()).all()
    return devices


@app.get("/api/devices/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, db: Session = Depends(get_db)):
    """获取设备详情"""
    device = db.query(Device).filter_by(device_id=device_id).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return device


@app.post("/api/devices/{device_id}/execute", response_model=CommandResponse)
def execute_command(
    device_id: str,
    request: CommandRequest,
    db: Session = Depends(get_db)
):
    """在设备上执行命令"""
    # 检查设备是否存在
    device = db.query(Device).filter_by(device_id=device_id).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.status != "online":
        raise HTTPException(status_code=400, detail="Device is offline")
    
    # 创建命令
    command_id = f"cmd-{uuid.uuid4().hex[:12]}"
    
    command = Command(
        command_id=command_id,
        device_id=device_id,
        command_type=request.command_type,
        payload=json.dumps(request.payload),
        timeout=request.timeout,
        status="pending",
        created_by="api"
    )
    
    db.add(command)
    
    # 记录审计日志
    audit = AuditLog(
        device_id=device_id,
        action="execute_command",
        details={
            "command_id": command_id,
            "command_type": request.command_type,
            "payload": request.payload
        }
    )
    db.add(audit)
    
    db.commit()
    db.refresh(command)
    
    return command


@app.get("/api/commands/{command_id}", response_model=CommandResponse)
def get_command(command_id: str, db: Session = Depends(get_db)):
    """获取命令详情"""
    command = db.query(Command).filter_by(command_id=command_id).first()
    
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    
    return command


@app.get("/api/devices/{device_id}/commands", response_model=List[CommandResponse])
def list_device_commands(
    device_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取设备的命令历史"""
    query = db.query(Command).filter_by(device_id=device_id)
    
    if status:
        query = query.filter(Command.status == status)
    
    commands = query.order_by(Command.created_at.desc()).limit(limit).all()
    return commands


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """获取统计信息"""
    total_devices = db.query(Device).count()
    online_devices = db.query(Device).filter_by(status="online").count()
    offline_devices = db.query(Device).filter_by(status="offline").count()
    
    total_commands = db.query(Command).count()
    pending_commands = db.query(Command).filter_by(status="pending").count()
    running_commands = db.query(Command).filter_by(status="running").count()
    completed_commands = db.query(Command).filter_by(status="completed").count()
    failed_commands = db.query(Command).filter_by(status="failed").count()
    
    return {
        "devices": {
            "total": total_devices,
            "online": online_devices,
            "offline": offline_devices
        },
        "commands": {
            "total": total_commands,
            "pending": pending_commands,
            "running": running_commands,
            "completed": completed_commands,
            "failed": failed_commands
        }
    }


# ============================================
# 健康检查
# ============================================

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy"}


# ============================================
# 启动
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
