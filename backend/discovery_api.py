"""
N8枢纽控制中心 - 功能发现API模块
提供系统功能列表、权限列表、API版本信息的查询接口
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query

from auth_middleware import require_auth


# API版本信息
API_VERSION = {
    "version": "1.0.0",
    "release_date": "2025-12-12",
    "api_base_url": "/api/v1",
    "supported_auth_methods": ["session_token", "api_key"],
    "min_client_version": "1.0.0"
}


# 系统功能清单
SYSTEM_CAPABILITIES = {
    "device_management": {
        "name": "设备管理",
        "description": "管理和监控设备",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/devices", "description": "列出所有设备"},
            {"method": "GET", "path": "/api/v1/devices/{device_id}", "description": "获取设备详情"},
            {"method": "POST", "path": "/api/v1/devices", "description": "注册新设备"},
            {"method": "PUT", "path": "/api/v1/devices/{device_id}", "description": "更新设备信息"},
            {"method": "DELETE", "path": "/api/v1/devices/{device_id}", "description": "删除设备"}
        ],
        "required_permissions": ["device:read", "device:write", "device:delete"],
        "available_for": ["web", "external", "internal"]
    },
    "command_execution": {
        "name": "命令执行",
        "description": "在设备上执行命令",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/devices/{device_id}/command", "description": "执行命令"},
            {"method": "GET", "path": "/api/v1/devices/{device_id}/command/{command_id}", "description": "查询命令状态"},
            {"method": "GET", "path": "/api/v1/devices/{device_id}/commands", "description": "列出命令历史"}
        ],
        "required_permissions": ["device:control", "command:execute"],
        "available_for": ["web", "external", "internal"]
    },
    "file_management": {
        "name": "文件管理",
        "description": "上传、下载、管理设备文件",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/devices/{device_id}/files", "description": "列出文件"},
            {"method": "POST", "path": "/api/v1/devices/{device_id}/files/upload", "description": "上传文件"},
            {"method": "GET", "path": "/api/v1/devices/{device_id}/files/download", "description": "下载文件"},
            {"method": "DELETE", "path": "/api/v1/devices/{device_id}/files", "description": "删除文件"}
        ],
        "required_permissions": ["file:read", "file:write", "file:delete"],
        "available_for": ["web", "external", "internal"]
    },
    "process_management": {
        "name": "进程管理",
        "description": "查看和管理设备进程",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/devices/{device_id}/processes", "description": "列出进程"},
            {"method": "GET", "path": "/api/v1/devices/{device_id}/processes/{pid}", "description": "获取进程详情"},
            {"method": "POST", "path": "/api/v1/devices/{device_id}/processes/{pid}/kill", "description": "终止进程"}
        ],
        "required_permissions": ["process:read", "process:control"],
        "available_for": ["web", "external", "internal"]
    },
    "system_monitoring": {
        "name": "系统监控",
        "description": "监控设备系统资源和性能",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/devices/{device_id}/metrics", "description": "获取实时指标"},
            {"method": "GET", "path": "/api/v1/devices/{device_id}/metrics/history", "description": "获取历史指标"},
            {"method": "GET", "path": "/api/v1/devices/{device_id}/health", "description": "健康检查"}
        ],
        "required_permissions": ["metrics:read"],
        "available_for": ["web", "external", "internal"]
    },
    "workflow_orchestration": {
        "name": "工作流编排",
        "description": "创建和执行自动化工作流",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/workflows", "description": "列出工作流"},
            {"method": "POST", "path": "/api/v1/workflows", "description": "创建工作流"},
            {"method": "POST", "path": "/api/v1/workflows/{workflow_id}/execute", "description": "执行工作流"},
            {"method": "GET", "path": "/api/v1/workflows/{workflow_id}/status", "description": "查询工作流状态"}
        ],
        "required_permissions": ["workflow:read", "workflow:write", "workflow:execute"],
        "available_for": ["web", "external"]
    },
    "log_management": {
        "name": "日志管理",
        "description": "查询和管理系统日志",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/logs", "description": "查询日志"},
            {"method": "GET", "path": "/api/v1/logs/export", "description": "导出日志"},
            {"method": "DELETE", "path": "/api/v1/logs", "description": "清理日志"}
        ],
        "required_permissions": ["log:read", "log:delete"],
        "available_for": ["web"]
    },
    "api_key_management": {
        "name": "API Key管理",
        "description": "管理API Key和权限",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/api-keys", "description": "列出API Key"},
            {"method": "POST", "path": "/api/v1/api-keys", "description": "创建API Key"},
            {"method": "PUT", "path": "/api/v1/api-keys/{key_id}", "description": "更新API Key"},
            {"method": "DELETE", "path": "/api/v1/api-keys/{key_id}", "description": "删除API Key"}
        ],
        "required_permissions": ["admin:api_keys"],
        "available_for": ["web"]
    },
    "session_management": {
        "name": "会话管理",
        "description": "管理用户会话",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/auth/login", "description": "登录（创建Session）"},
            {"method": "POST", "path": "/api/v1/auth/logout", "description": "登出（删除Session）"},
            {"method": "POST", "path": "/api/v1/auth/refresh", "description": "刷新Session"},
            {"method": "GET", "path": "/api/v1/auth/sessions", "description": "列出活跃Session"}
        ],
        "required_permissions": [],
        "available_for": ["web", "external", "internal"]
    }
}


# 权限清单
PERMISSION_DEFINITIONS = {
    "device:read": {
        "name": "设备读取",
        "description": "查看设备列表和详情",
        "category": "device_management"
    },
    "device:write": {
        "name": "设备写入",
        "description": "创建和更新设备信息",
        "category": "device_management"
    },
    "device:delete": {
        "name": "设备删除",
        "description": "删除设备",
        "category": "device_management"
    },
    "device:control": {
        "name": "设备控制",
        "description": "控制设备（执行命令等）",
        "category": "command_execution"
    },
    "command:execute": {
        "name": "命令执行",
        "description": "在设备上执行命令",
        "category": "command_execution"
    },
    "file:read": {
        "name": "文件读取",
        "description": "查看和下载设备文件",
        "category": "file_management"
    },
    "file:write": {
        "name": "文件写入",
        "description": "上传和修改设备文件",
        "category": "file_management"
    },
    "file:delete": {
        "name": "文件删除",
        "description": "删除设备文件",
        "category": "file_management"
    },
    "process:read": {
        "name": "进程读取",
        "description": "查看设备进程信息",
        "category": "process_management"
    },
    "process:control": {
        "name": "进程控制",
        "description": "启动、停止、重启进程",
        "category": "process_management"
    },
    "metrics:read": {
        "name": "指标读取",
        "description": "查看设备性能指标",
        "category": "system_monitoring"
    },
    "workflow:read": {
        "name": "工作流读取",
        "description": "查看工作流列表和详情",
        "category": "workflow_orchestration"
    },
    "workflow:write": {
        "name": "工作流写入",
        "description": "创建和修改工作流",
        "category": "workflow_orchestration"
    },
    "workflow:execute": {
        "name": "工作流执行",
        "description": "执行工作流",
        "category": "workflow_orchestration"
    },
    "log:read": {
        "name": "日志读取",
        "description": "查看系统日志",
        "category": "log_management"
    },
    "log:delete": {
        "name": "日志删除",
        "description": "清理系统日志",
        "category": "log_management"
    },
    "admin:api_keys": {
        "name": "API Key管理",
        "description": "管理API Key和权限",
        "category": "api_key_management"
    },
    "admin:write": {
        "name": "系统管理",
        "description": "修改系统设置",
        "category": "system_administration"
    }
}


# API类型说明
API_TYPE_DESCRIPTIONS = {
    "web": {
        "name": "Web视窗控制API",
        "description": "用于Web前端界面，支持人类交互操作",
        "authentication": "Session Token（72小时有效期）",
        "typical_use_cases": ["Web控制台", "管理后台", "可视化界面"]
    },
    "external": {
        "name": "外网API",
        "description": "从VPS1进入的外部API，主要供Manus AI使用",
        "authentication": "API Key + Secret",
        "typical_use_cases": ["Manus AI控制", "外部系统集成", "远程自动化"]
    },
    "internal": {
        "name": "内网AI智能体API",
        "description": "本地开源模型使用的内网API",
        "authentication": "API Key + Secret",
        "typical_use_cases": ["本地AI助手", "内网自动化", "离线智能体"]
    }
}


# 创建API路由
router = APIRouter(prefix="/api/v1/discovery", tags=["Discovery"])


@router.get("/version")
async def get_api_version():
    """
    获取API版本信息
    
    返回：
    - version: API版本号
    - release_date: 发布日期
    - api_base_url: API基础URL
    - supported_auth_methods: 支持的认证方式
    - min_client_version: 最低客户端版本要求
    """
    return {
        "status": "success",
        "data": API_VERSION,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/capabilities")
async def get_capabilities(
    api_type: Optional[str] = Query(None, description="过滤API类型（web/external/internal）"),
    category: Optional[str] = Query(None, description="过滤功能类别"),
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    获取系统功能列表
    
    参数：
    - api_type: 过滤API类型（可选）
    - category: 过滤功能类别（可选）
    
    返回：
    - capabilities: 功能列表
    - total_count: 功能总数
    """
    # 获取用户的API类型
    if 'api_key' in auth_info:
        user_api_type = auth_info['api_key']['api_type']
    else:
        user_api_type = auth_info['api_type']
    
    # 过滤功能
    filtered_capabilities = {}
    
    for cap_id, cap_info in SYSTEM_CAPABILITIES.items():
        # 检查API类型过滤
        if api_type and api_type not in cap_info['available_for']:
            continue
        
        # 检查用户API类型权限
        if user_api_type not in cap_info['available_for']:
            continue
        
        # 检查类别过滤
        if category and cap_id != category:
            continue
        
        filtered_capabilities[cap_id] = cap_info
    
    return {
        "status": "success",
        "data": {
            "capabilities": filtered_capabilities,
            "total_count": len(filtered_capabilities),
            "user_api_type": user_api_type
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/permissions")
async def get_permissions(
    category: Optional[str] = Query(None, description="过滤权限类别"),
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    获取权限列表
    
    参数：
    - category: 过滤权限类别（可选）
    
    返回：
    - permissions: 权限列表
    - user_permissions: 用户拥有的权限
    - total_count: 权限总数
    """
    # 获取用户权限
    if 'api_key' in auth_info:
        user_permissions = auth_info['api_key'].get('permissions', [])
    else:
        user_permissions = auth_info.get('permissions', [])
    
    # 过滤权限
    filtered_permissions = {}
    
    for perm_id, perm_info in PERMISSION_DEFINITIONS.items():
        # 检查类别过滤
        if category and perm_info['category'] != category:
            continue
        
        # 添加用户是否拥有该权限的标记
        perm_info_with_status = {
            **perm_info,
            "granted": perm_id in user_permissions
        }
        
        filtered_permissions[perm_id] = perm_info_with_status
    
    return {
        "status": "success",
        "data": {
            "permissions": filtered_permissions,
            "user_permissions": user_permissions,
            "total_count": len(filtered_permissions)
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/api-types")
async def get_api_types():
    """
    获取API类型说明
    
    返回：
    - api_types: API类型列表及说明
    """
    return {
        "status": "success",
        "data": {
            "api_types": API_TYPE_DESCRIPTIONS
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/endpoints")
async def get_endpoints(
    capability: Optional[str] = Query(None, description="过滤功能类别"),
    method: Optional[str] = Query(None, description="过滤HTTP方法（GET/POST/PUT/DELETE）"),
    auth_info: Dict[str, Any] = Depends(require_auth)
):
    """
    获取API端点列表
    
    参数：
    - capability: 过滤功能类别（可选）
    - method: 过滤HTTP方法（可选）
    
    返回：
    - endpoints: 端点列表
    - total_count: 端点总数
    """
    # 获取用户的API类型
    if 'api_key' in auth_info:
        user_api_type = auth_info['api_key']['api_type']
    else:
        user_api_type = auth_info['api_type']
    
    # 收集所有端点
    all_endpoints = []
    
    for cap_id, cap_info in SYSTEM_CAPABILITIES.items():
        # 检查功能过滤
        if capability and cap_id != capability:
            continue
        
        # 检查用户API类型权限
        if user_api_type not in cap_info['available_for']:
            continue
        
        # 添加端点
        for endpoint in cap_info['endpoints']:
            # 检查方法过滤
            if method and endpoint['method'] != method.upper():
                continue
            
            all_endpoints.append({
                **endpoint,
                "capability": cap_id,
                "capability_name": cap_info['name'],
                "required_permissions": cap_info['required_permissions']
            })
    
    return {
        "status": "success",
        "data": {
            "endpoints": all_endpoints,
            "total_count": len(all_endpoints),
            "user_api_type": user_api_type
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health")
async def health_check():
    """
    健康检查（无需认证）
    
    返回：
    - status: 服务状态
    - version: API版本
    """
    return {
        "status": "healthy",
        "version": API_VERSION['version'],
        "timestamp": datetime.now().isoformat()
    }
