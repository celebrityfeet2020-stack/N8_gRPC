"""
N8枢纽控制中心 - 主应用入口
FastAPI应用，集成所有模块的路由
包含M1-M4模块
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
    description="AI友好的设备远程控制系统 - M1核心基础 + M4文件管理",
    version="2.0.0",
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


# 根路径
@app.get("/")
async def root():
    """根路径 - 系统信息"""
    return {
        "name": "N8 Hub Control Center API",
        "version": "2.0.0",
        "stage": "M1 + M4",
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
                "list_result": "GET /api/v1/files/list/{task_id}",
                "list_tasks": "GET /api/v1/files/list",
                "upload": "POST /api/v1/files/upload",
                "upload_chunk": "POST /api/v1/files/upload/{task_id}/chunk/{chunk_index}",
                "upload_result": "GET /api/v1/files/upload/{task_id}",
                "upload_tasks": "GET /api/v1/files/upload",
                "download": "POST /api/v1/files/download",
                "download_upload": "POST /api/v1/files/download/{task_id}/upload",
                "download_result": "GET /api/v1/files/download/{task_id}",
                "download_file": "GET /api/v1/files/download/{task_id}/file",
                "download_tasks": "GET /api/v1/files/download",
                "operations": "POST /api/v1/files/operations",
                "operations_result": "GET /api/v1/files/operations/{task_id}",
                "operations_tasks": "GET /api/v1/files/operations",
                "operations_update": "POST /api/v1/files/operations/{task_id}/update"
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
            "M4-04": "File Operations"
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
