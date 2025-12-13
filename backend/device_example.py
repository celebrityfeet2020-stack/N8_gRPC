"""
N8枢纽控制中心 - 设备注册使用示例
演示如何在FastAPI应用中集成设备注册API
"""

from fastapi import FastAPI
from device_registration import router as device_router, init_device_manager
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
    database_url = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
    
    # 初始化认证中间件
    init_auth_middleware(database_url)
    print("✅ 认证中间件已初始化")
    
    # 初始化设备注册管理器
    init_device_manager(database_url)
    print("✅ 设备注册管理器已初始化")


# 注册设备API路由
app.include_router(device_router)


# ==================== 根路径 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "N8 Hub Control Center API",
        "version": "1.0.0",
        "documentation": "/docs",
        "device_endpoints": {
            "register": "POST /api/v1/devices/register",
            "list": "GET /api/v1/devices",
            "get": "GET /api/v1/devices/{device_id}",
            "update": "PUT /api/v1/devices/{device_id}",
            "delete": "DELETE /api/v1/devices/{device_id}"
        }
    }


# ==================== 使用示例 ====================

"""
1. 注册设备（Agent调用）
   POST /api/v1/devices/register
   Header: Authorization: Bearer <session_token>
   Body: {
     "hostname": "ubuntu-server",
     "ip_address": "192.168.9.125",
     "os_type": "linux",
     "os_version": "Ubuntu 22.04 LTS",
     "agent_version": "1.0.0",
     "metadata": {
       "cpu_cores": 8,
       "memory_gb": 16
     }
   }
   
   响应示例：
   {
     "status": "success",
     "message": "Device registered successfully",
     "data": {
       "id": 1,
       "device_id": "device-a1b2c3d4e5f6g7h8",
       "device_name": "ubuntu-server (192.168.9.125)",
       "hostname": "ubuntu-server",
       "ip_address": "192.168.9.125",
       "os_type": "linux",
       "os_version": "Ubuntu 22.04 LTS",
       "agent_version": "1.0.0",
       "status": "online",
       "last_seen": "2025-12-12T07:30:00",
       "registered_at": "2025-12-12T07:30:00",
       "metadata": {
         "cpu_cores": 8,
         "memory_gb": 16
       }
     }
   }

2. 列出所有设备
   GET /api/v1/devices
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "data": {
       "devices": [
         {
           "id": 1,
           "device_id": "device-a1b2c3d4e5f6g7h8",
           "device_name": "ubuntu-server (192.168.9.125)",
           "hostname": "ubuntu-server",
           "ip_address": "192.168.9.125",
           "os_type": "linux",
           "status": "online",
           "last_seen": "2025-12-12T07:30:00"
         },
         ...
       ],
       "total_count": 10,
       "limit": 100,
       "offset": 0
     }
   }

3. 过滤在线设备
   GET /api/v1/devices?status=online
   Header: Authorization: Bearer <session_token>

4. 过滤Linux设备
   GET /api/v1/devices?os_type=linux
   Header: Authorization: Bearer <session_token>

5. 分页查询
   GET /api/v1/devices?limit=20&offset=40
   Header: Authorization: Bearer <session_token>

6. 获取设备详情
   GET /api/v1/devices/device-a1b2c3d4e5f6g7h8
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "data": {
       "id": 1,
       "device_id": "device-a1b2c3d4e5f6g7h8",
       "device_name": "生产服务器-01",
       "hostname": "ubuntu-server",
       "ip_address": "192.168.9.125",
       "os_type": "linux",
       "os_version": "Ubuntu 22.04 LTS",
       "agent_version": "1.0.0",
       "status": "online",
       "last_seen": "2025-12-12T07:30:00",
       "registered_at": "2025-12-12T07:30:00",
       "description": "主要生产服务器",
       "tags": ["production", "web-server"],
       "metadata": {
         "cpu_cores": 8,
         "memory_gb": 16
       }
     }
   }

7. 更新设备信息（Web后台调用）
   PUT /api/v1/devices/device-a1b2c3d4e5f6g7h8
   Header: Authorization: Bearer <session_token>
   Body: {
     "device_name": "生产服务器-01",
     "description": "主要生产服务器",
     "tags": ["production", "web-server"]
   }
   
   响应示例：
   {
     "status": "success",
     "message": "Device updated successfully",
     "data": {
       "id": 1,
       "device_id": "device-a1b2c3d4e5f6g7h8",
       "device_name": "生产服务器-01",
       "description": "主要生产服务器",
       "tags": ["production", "web-server"],
       ...
     }
   }

8. 删除设备
   DELETE /api/v1/devices/device-a1b2c3d4e5f6g7h8
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "message": "Device deleted successfully"
   }
"""


# ==================== Agent使用示例 ====================

"""
Agent端代码示例（Python）：

import requests
import socket
import platform

class N8Agent:
    def __init__(self, api_url, api_key, api_secret):
        self.api_url = api_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.device_id = None
    
    def register(self):
        \"\"\"注册设备\"\"\"
        # 获取主机信息
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        os_type = platform.system().lower()
        os_version = platform.version()
        agent_version = "1.0.0"
        
        # 发送注册请求
        response = requests.post(
            f"{self.api_url}/api/v1/devices/register",
            headers={
                "X-API-Key": self.api_key,
                "X-API-Secret": self.api_secret
            },
            json={
                "hostname": hostname,
                "ip_address": ip_address,
                "os_type": os_type,
                "os_version": os_version,
                "agent_version": agent_version,
                "metadata": {
                    "cpu_cores": os.cpu_count(),
                    "memory_gb": round(psutil.virtual_memory().total / (1024**3), 2)
                }
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            self.device_id = data['data']['device_id']
            print(f"✅ 设备注册成功: {self.device_id}")
            return True
        else:
            print(f"❌ 设备注册失败: {response.text}")
            return False

# 使用示例
agent = N8Agent(
    api_url="http://192.168.9.113:14032",
    api_key="your_api_key",
    api_secret="your_api_secret"
)
agent.register()
"""


# ==================== AI智能体使用示例 ====================

"""
AI智能体可以通过设备注册API管理设备：

示例对话1：
User: "列出所有在线的Linux设备"
AI:
  1. 调用 GET /api/v1/devices?status=online&os_type=linux
  2. 解析响应，展示设备列表

示例对话2：
User: "把设备device-xxx重命名为'测试服务器'"
AI:
  1. 调用 PUT /api/v1/devices/device-xxx
  2. Body: {"device_name": "测试服务器"}
  3. 确认更新成功

示例对话3：
User: "删除离线超过7天的设备"
AI:
  1. 调用 GET /api/v1/devices?status=offline
  2. 筛选last_seen超过7天的设备
  3. 对每个设备调用 DELETE /api/v1/devices/{device_id}
  4. 汇报删除结果
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
