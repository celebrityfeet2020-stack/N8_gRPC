"""
N8枢纽控制中心 - 功能发现API使用示例
演示如何在FastAPI应用中集成功能发现API
"""

from fastapi import FastAPI
from discovery_api import router as discovery_router
from auth_middleware import init_auth_middleware


# 创建FastAPI应用
app = FastAPI(
    title="N8 Hub Control Center API",
    description="AI友好的设备远程控制系统",
    version="1.0.0"
)


# 应用启动时初始化
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # 初始化认证中间件
    database_url = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
    init_auth_middleware(database_url)
    print("✅ 认证中间件已初始化")


# 注册功能发现API路由
app.include_router(discovery_router)


# ==================== 根路径 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "N8 Hub Control Center API",
        "version": "1.0.0",
        "documentation": "/docs",
        "discovery": {
            "version": "/api/v1/discovery/version",
            "capabilities": "/api/v1/discovery/capabilities",
            "permissions": "/api/v1/discovery/permissions",
            "api_types": "/api/v1/discovery/api-types",
            "endpoints": "/api/v1/discovery/endpoints"
        }
    }


# ==================== 使用示例 ====================

"""
1. 获取API版本信息（无需认证）
   GET /api/v1/discovery/version
   
   响应示例：
   {
     "status": "success",
     "data": {
       "version": "1.0.0",
       "release_date": "2025-12-12",
       "api_base_url": "/api/v1",
       "supported_auth_methods": ["session_token", "api_key"],
       "min_client_version": "1.0.0"
     },
     "timestamp": "2025-12-12T07:00:00"
   }

2. 获取系统功能列表（需要认证）
   GET /api/v1/discovery/capabilities
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "data": {
       "capabilities": {
         "device_management": {
           "name": "设备管理",
           "description": "管理和监控设备",
           "endpoints": [...],
           "required_permissions": ["device:read", "device:write"],
           "available_for": ["web", "external", "internal"]
         },
         ...
       },
       "total_count": 9,
       "user_api_type": "web"
     },
     "timestamp": "2025-12-12T07:00:00"
   }

3. 获取权限列表（需要认证）
   GET /api/v1/discovery/permissions
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "data": {
       "permissions": {
         "device:read": {
           "name": "设备读取",
           "description": "查看设备列表和详情",
           "category": "device_management",
           "granted": true
         },
         ...
       },
       "user_permissions": ["device:read", "device:write"],
       "total_count": 18
     },
     "timestamp": "2025-12-12T07:00:00"
   }

4. 获取API类型说明（无需认证）
   GET /api/v1/discovery/api-types
   
   响应示例：
   {
     "status": "success",
     "data": {
       "api_types": {
         "web": {
           "name": "Web视窗控制API",
           "description": "用于Web前端界面，支持人类交互操作",
           "authentication": "Session Token（72小时有效期）",
           "typical_use_cases": ["Web控制台", "管理后台"]
         },
         ...
       }
     },
     "timestamp": "2025-12-12T07:00:00"
   }

5. 获取API端点列表（需要认证）
   GET /api/v1/discovery/endpoints?capability=device_management
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "data": {
       "endpoints": [
         {
           "method": "GET",
           "path": "/api/v1/devices",
           "description": "列出所有设备",
           "capability": "device_management",
           "capability_name": "设备管理",
           "required_permissions": ["device:read"]
         },
         ...
       ],
       "total_count": 5,
       "user_api_type": "web"
     },
     "timestamp": "2025-12-12T07:00:00"
   }

6. 健康检查（无需认证）
   GET /api/v1/discovery/health
   
   响应示例：
   {
     "status": "healthy",
     "version": "1.0.0",
     "timestamp": "2025-12-12T07:00:00"
   }
"""


# ==================== AI智能体使用示例 ====================

"""
AI智能体可以通过功能发现API了解系统能力：

1. 首先获取系统功能列表：
   GET /api/v1/discovery/capabilities
   
2. 根据需要选择功能类别：
   - device_management: 管理设备
   - command_execution: 执行命令
   - file_management: 文件操作
   - process_management: 进程管理
   - system_monitoring: 系统监控
   - workflow_orchestration: 工作流
   
3. 查看所需权限：
   GET /api/v1/discovery/permissions
   
4. 确认自己拥有的权限后，调用相应的API端点

示例对话：
User: "帮我列出所有设备"
AI: 
  1. 调用 GET /api/v1/discovery/capabilities 了解系统功能
  2. 发现 device_management 功能，需要 device:read 权限
  3. 调用 GET /api/v1/discovery/permissions 确认拥有该权限
  4. 调用 GET /api/v1/devices 列出设备
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
