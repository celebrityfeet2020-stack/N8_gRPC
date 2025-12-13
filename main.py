"""
N8枢纽控制中心 - 主应用入口
FastAPI应用，集成所有模块的路由
包含M1-M6模块
"""

import os
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 导入M1路由
from discovery_api import router as discovery_router
from device_registration import router as device_router, init_device_manager
from heartbeat import router as heartbeat_router, init_heartbeat_manager

# 导入M4路由
from file_list import router as file_list_router, init_file_list_manager
from file_upload import router as file_upload_router, init_file_upload_manager
from file_download import router as file_download_router, init_file_download_manager
from file_operations import router as file_operations_router, init_file_operation_manager

# 导入M5路由
from process_management import router as process_router, init_process_manager

# 导入M6路由
from system_monitoring import router as monitoring_router, init_system_monitoring_manager

# 导入认证中间件
from auth_middleware import init_auth_middleware


# 数据库连接URL（从环境变量读取）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
)


# 应用生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的处理"""
    # 启动时初始化
    print("=" * 60)
    print("N8 Hub Control Center - Starting")
    print("=" * 60)
    print(f"Database URL: {DATABASE_URL}")
    print()
    
    # 初始化认证中间件
    init_auth_middleware(DATABASE_URL)
    print("✅ 认证中间件已初始化")
    
    # 初始化M1管理器
    init_device_manager(DATABASE_URL)
    print("✅ 设备注册管理器已初始化")
    
    init_heartbeat_manager(DATABASE_URL)
    print("✅ 心跳管理器已初始化")
    
    # 初始化M4管理器
    init_file_list_manager(DATABASE_URL)
    print("✅ 文件列表管理器已初始化")
    
    init_file_upload_manager(DATABASE_URL)
    print("✅ 文件上传管理器已初始化")
    
    init_file_download_manager(DATABASE_URL)
    print("✅ 文件下载管理器已初始化")
    
    init_file_operation_manager(DATABASE_URL)
    print("✅ 文件操作管理器已初始化")
    
    # 初始化M5管理器
    init_process_manager(DATABASE_URL)
    print("✅ 进程管理器已初始化")
    
    # 初始化M6管理器
    init_system_monitoring_manager(DATABASE_URL)
    print("✅ 系统监控管理器已初始化")
    
    print()
    print("=" * 60)
    print("N8 Hub Control Center - Ready")
    print("=" * 60)
    print()
    
    yield
    
    # 关闭时清理
    print()
    print("=" * 60)
    print("N8 Hub Control Center - Shutting down")
    print("=" * 60)


# 创建FastAPI应用
app = FastAPI(
    title="N8 Hub Control Center API",
    description="AI友好的设备远程控制系统 - M1核心基础 + M4文件管理 + M5进程管理 + M6系统监控",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# 配置CORS（允许所有来源，生产环境需要限制）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该指定具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册路由
# M1路由
app.include_router(discovery_router)  # 功能发现API
app.include_router(device_router)     # 设备管理API
app.include_router(heartbeat_router)  # 心跳检测API

# M4路由
app.include_router(file_list_router)       # 文件列表查询
app.include_router(file_upload_router)     # 文件上传
app.include_router(file_download_router)   # 文件下载
app.include_router(file_operations_router) # 文件操作

# M5路由
app.include_router(process_router)         # 进程管理

# M6路由
app.include_router(monitoring_router)      # 系统监控


# 根路径
@app.get("/")
async def root():
    """根路径 - 系统信息"""
    return {
        "name": "N8 Hub Control Center API",
        "version": "3.0.0",
        "stage": "M1 + M4 + M5 + M6",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "discovery": {
                "version": "GET /api/v1/discovery/version",
                "capabilities": "GET /api/v1/discovery/capabilities",
                "permissions": "GET /api/v1/discovery/permissions",
                "api_types": "GET /api/v1/discovery/api-types",
                "endpoints": "GET /api/v1/discovery/endpoints",
                "health": "GET /api/v1/discovery/health"
            },
            "devices": {
                "register": "POST /api/v1/devices/register",
                "list": "GET /api/v1/devices",
                "get": "GET /api/v1/devices/{device_id}",
                "update": "PUT /api/v1/devices/{device_id}",
                "delete": "DELETE /api/v1/devices/{device_id}"
            },
            "heartbeat": {
                "report": "POST /api/v1/devices/{device_id}/heartbeat",
                "status": "GET /api/v1/devices/{device_id}/heartbeat",
                "statistics": "GET /api/v1/devices/heartbeat/statistics",
                "check_offline": "POST /api/v1/devices/heartbeat/check-offline"
            },
            "files": {
                "list": "POST /api/v1/files/list",
                "upload": "POST /api/v1/files/upload",
                "download": "POST /api/v1/files/download",
                "operations": "POST /api/v1/files/operations"
            },
            "processes": {
                "list": "POST /api/v1/processes/list",
                "kill": "POST /api/v1/processes/kill",
                "start": "POST /api/v1/processes/start",
                "detail": "GET /api/v1/processes/detail/{task_id}/{pid}"
            },
            "monitoring": {
                "system_info": "GET /api/v1/monitoring/system-info/{device_id}",
                "network_interfaces": "GET /api/v1/monitoring/network-interfaces/{device_id}",
                "network_traffic": "GET /api/v1/monitoring/network-traffic/{device_id}",
                "process_guards": "GET /api/v1/monitoring/process-guards/{device_id}",
                "performance_history": "GET /api/v1/monitoring/performance-history/{device_id}",
                "network_connections": "GET /api/v1/monitoring/network-connections/{device_id}"
            }
        },
        "modules": {
            "M1-01": "Database Schema",
            "M1-02": "API Key Management",
            "M1-03": "Session Management",
            "M1-04": "Authentication Middleware",
            "M1-05": "Discovery API",
            "M1-06": "Device Registration",
            "M1-07": "Heartbeat Detection",
            "M4-01": "File List Query",
            "M4-02": "File Upload",
            "M4-03": "File Download",
            "M4-04": "File Operations",
            "M5-01": "Process List Query",
            "M5-02": "Process Kill",
            "M5-03": "Process Start",
            "M5-04": "Process Detail",
            "M6-01": "System Info Collection",
            "M6-02": "Network Info Query",
            "M6-03": "Network Traffic Monitoring",
            "M6-04": "Process Guard",
            "M6-05": "Windows Event Log",
            "M6-06": "Performance History",
            "M6-07": "Network Connection Query"
        }
    }


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# 如果直接运行此文件
if __name__ == "__main__":
    import uvicorn
    
    # 从环境变量读取配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "18032"))
    
    print(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,  # 生产环境不使用reload
        log_level="info"
    )
