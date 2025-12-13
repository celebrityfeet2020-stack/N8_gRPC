"""
N8枢纽控制中心 - 认证中间件使用示例
演示如何在FastAPI中使用认证中间件
"""

from fastapi import FastAPI, Depends
from typing import Dict, Any

from auth_middleware import (
    init_auth_middleware,
    get_auth_middleware,
    require_session,
    require_api_key,
    require_auth
)


# 创建FastAPI应用
app = FastAPI(title="N8 Hub Control Center API")


# 应用启动时初始化认证中间件
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    database_url = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
    init_auth_middleware(database_url)
    print("✅ 认证中间件已初始化")


# ==================== 示例1：要求Session Token认证 ====================

@app.get("/api/v1/profile")
async def get_profile(session_info: Dict[str, Any] = Depends(require_session)):
    """
    获取用户资料（需要Session Token）
    
    使用方式：
    curl -H "Authorization: Bearer <session_token>" http://localhost:8000/api/v1/profile
    """
    return {
        "message": "Profile retrieved successfully",
        "session_id": session_info['id'],
        "api_key_name": session_info['api_key']['api_name'],
        "api_type": session_info['api_key']['api_type']
    }


# ==================== 示例2：要求API Key认证 ====================

@app.get("/api/v1/devices")
async def list_devices(api_key_info: Dict[str, Any] = Depends(require_api_key)):
    """
    列出设备（需要API Key）
    
    使用方式：
    curl -H "X-API-Key: <api_key>" -H "X-API-Secret: <secret>" http://localhost:8000/api/v1/devices
    """
    return {
        "message": "Devices retrieved successfully",
        "api_key_name": api_key_info['api_name'],
        "api_type": api_key_info['api_type'],
        "devices": []  # 实际应该从数据库查询
    }


# ==================== 示例3：Session Token或API Key都可以 ====================

@app.get("/api/v1/status")
async def get_status(auth_info: Dict[str, Any] = Depends(require_auth)):
    """
    获取系统状态（Session Token或API Key都可以）
    
    使用方式1（Session Token）：
    curl -H "Authorization: Bearer <session_token>" http://localhost:8000/api/v1/status
    
    使用方式2（API Key）：
    curl -H "X-API-Key: <api_key>" -H "X-API-Secret: <secret>" http://localhost:8000/api/v1/status
    """
    # 判断是Session还是API Key
    if 'api_key' in auth_info:
        auth_type = "session"
        api_name = auth_info['api_key']['api_name']
    else:
        auth_type = "api_key"
        api_name = auth_info['api_name']
    
    return {
        "message": "Status retrieved successfully",
        "auth_type": auth_type,
        "api_name": api_name,
        "status": "healthy"
    }


# ==================== 示例4：检查权限 ====================

@app.post("/api/v1/devices/{device_id}/command")
async def send_command(
    device_id: str,
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    发送命令到设备（需要device:control权限）
    
    使用方式：
    curl -X POST -H "Authorization: Bearer <session_token>" \
         http://localhost:8000/api/v1/devices/device-001/command
    """
    # 获取认证中间件实例
    auth = get_auth_middleware()
    
    # 检查权限
    required_permissions = ["device:control"]
    if not auth.check_permissions(auth_info, required_permissions):
        return {
            "error": "Permission denied",
            "required_permissions": required_permissions
        }, 403
    
    return {
        "message": "Command sent successfully",
        "device_id": device_id
    }


# ==================== 示例5：使用权限依赖 ====================

@app.delete("/api/v1/devices/{device_id}")
async def delete_device(
    device_id: str,
    auth_info: Dict[str, Any] = Depends(
        get_auth_middleware().require_permissions(["device:delete"])
    )
):
    """
    删除设备（需要device:delete权限）
    
    使用方式：
    curl -X DELETE -H "Authorization: Bearer <session_token>" \
         http://localhost:8000/api/v1/devices/device-001
    """
    return {
        "message": "Device deleted successfully",
        "device_id": device_id
    }


# ==================== 示例6：检查API类型 ====================

@app.get("/api/v1/admin/logs")
async def get_admin_logs(
    auth_info: Dict[str, Any] = Depends(
        get_auth_middleware().require_api_type(["web"])
    )
):
    """
    获取管理日志（只允许Web API访问）
    
    使用方式：
    curl -H "Authorization: Bearer <session_token>" \
         http://localhost:8000/api/v1/admin/logs
    """
    return {
        "message": "Admin logs retrieved successfully",
        "logs": []
    }


# ==================== 示例7：组合多个检查 ====================

@app.post("/api/v1/admin/settings")
async def update_settings(
    auth_info: Dict[str, Any] = Depends(
        get_auth_middleware().require_permissions(["admin:write"])
    )
):
    """
    更新系统设置（需要admin:write权限，且只允许Web API）
    
    使用方式：
    curl -X POST -H "Authorization: Bearer <session_token>" \
         http://localhost:8000/api/v1/admin/settings
    """
    # 额外检查API类型
    auth = get_auth_middleware()
    
    # 获取API类型
    if 'api_key' in auth_info:
        api_type = auth_info['api_key']['api_type']
    else:
        api_type = auth_info['api_type']
    
    if api_type != "web":
        return {
            "error": "This endpoint is only accessible via Web API"
        }, 403
    
    return {
        "message": "Settings updated successfully"
    }


# ==================== 公开端点（无需认证） ====================

@app.get("/")
async def root():
    """根路径（无需认证）"""
    return {
        "message": "N8 Hub Control Center API",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """健康检查（无需认证）"""
    return {
        "status": "healthy",
        "timestamp": "2025-12-12T06:50:00Z"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
