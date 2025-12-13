"""
N8枢纽控制中心 - 心跳检测使用示例
演示如何在FastAPI应用中集成心跳检测API
"""

from fastapi import FastAPI
from heartbeat import router as heartbeat_router, init_heartbeat_manager
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
    
    # 初始化心跳管理器
    init_heartbeat_manager(database_url)
    print("✅ 心跳管理器已初始化")


# 注册心跳API路由
app.include_router(heartbeat_router)


# ==================== 根路径 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "N8 Hub Control Center API",
        "version": "1.0.0",
        "documentation": "/docs",
        "heartbeat_endpoints": {
            "report": "POST /api/v1/devices/{device_id}/heartbeat",
            "status": "GET /api/v1/devices/{device_id}/heartbeat",
            "statistics": "GET /api/v1/devices/heartbeat/statistics",
            "check_offline": "POST /api/v1/devices/heartbeat/check-offline"
        }
    }


# ==================== 使用示例 ====================

"""
1. 上报心跳（Agent定期调用，建议60秒间隔）
   POST /api/v1/devices/{device_id}/heartbeat
   Header: Authorization: Bearer <session_token>
   或
   Header: X-API-Key: <api_key>
           X-API-Secret: <api_secret>
   
   Body: {
     "metrics": {
       "cpu_usage": 45.2,
       "memory_usage": 68.5,
       "disk_usage": 72.3,
       "network_in": 1024000,
       "network_out": 512000
     },
     "metadata": {
       "uptime": 86400,
       "load_average": [1.5, 1.2, 1.0]
     }
   }
   
   响应示例：
   {
     "status": "success",
     "message": "Heartbeat reported successfully",
     "data": {
       "device_id": "device-a1b2c3d4e5f6g7h8",
       "status": "online",
       "last_seen": "2025-12-12T08:00:00",
       "next_heartbeat": 300
     }
   }

2. 获取设备心跳状态
   GET /api/v1/devices/{device_id}/heartbeat
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "data": {
       "device_id": "device-a1b2c3d4e5f6g7h8",
       "device_name": "生产服务器-01",
       "status": "online",
       "last_seen": "2025-12-12T08:00:00",
       "offline_duration": 30.5,
       "is_timeout": false,
       "heartbeat_timeout": 300,
       "registered_at": "2025-12-12T07:00:00"
     }
   }

3. 获取心跳统计信息
   GET /api/v1/devices/heartbeat/statistics
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "data": {
       "total_devices": 10,
       "online_devices": 8,
       "offline_devices": 2,
       "recent_active_devices": 7,
       "heartbeat_timeout": 300,
       "timestamp": "2025-12-12T08:00:00"
     }
   }

4. 手动触发离线检测（管理员功能）
   POST /api/v1/devices/heartbeat/check-offline
   Header: Authorization: Bearer <session_token>
   
   响应示例：
   {
     "status": "success",
     "message": "Offline check completed, 2 devices marked as offline",
     "data": {
       "offline_devices": [
         "device-xxx",
         "device-yyy"
       ],
       "count": 2
     }
   }
"""


# ==================== Agent使用示例 ====================

"""
Agent端代码示例（Python）：

import requests
import time
import psutil
from threading import Thread

class N8Agent:
    def __init__(self, api_url, api_key, api_secret, device_id):
        self.api_url = api_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.device_id = device_id
        self.heartbeat_interval = 60  # 60秒
        self.running = False
    
    def get_metrics(self):
        \"\"\"获取设备指标\"\"\"
        return {
            "cpu_usage": psutil.cpu_percent(interval=1),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "network_in": psutil.net_io_counters().bytes_recv,
            "network_out": psutil.net_io_counters().bytes_sent
        }
    
    def report_heartbeat(self):
        \"\"\"上报心跳\"\"\"
        try:
            metrics = self.get_metrics()
            
            response = requests.post(
                f"{self.api_url}/api/v1/devices/{self.device_id}/heartbeat",
                headers={
                    "X-API-Key": self.api_key,
                    "X-API-Secret": self.api_secret
                },
                json={
                    "metrics": metrics,
                    "metadata": {
                        "uptime": int(time.time() - psutil.boot_time())
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 心跳上报成功: {data['data']['status']}")
                return True
            else:
                print(f"❌ 心跳上报失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 心跳上报异常: {e}")
            return False
    
    def heartbeat_loop(self):
        \"\"\"心跳循环\"\"\"
        while self.running:
            self.report_heartbeat()
            time.sleep(self.heartbeat_interval)
    
    def start(self):
        \"\"\"启动心跳\"\"\"
        self.running = True
        thread = Thread(target=self.heartbeat_loop, daemon=True)
        thread.start()
        print(f"✅ 心跳已启动（间隔：{self.heartbeat_interval}秒）")
    
    def stop(self):
        \"\"\"停止心跳\"\"\"
        self.running = False
        print("✅ 心跳已停止")

# 使用示例
agent = N8Agent(
    api_url="http://192.168.9.113:14032",
    api_key="your_api_key",
    api_secret="your_api_secret",
    device_id="device-a1b2c3d4e5f6g7h8"
)

# 启动心跳
agent.start()

# 保持运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    agent.stop()
"""


# ==================== 定时任务示例 ====================

"""
使用APScheduler实现定时离线检测：

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from heartbeat import get_heartbeat_manager

scheduler = AsyncIOScheduler()

async def check_offline_devices_task():
    \"\"\"定时检查离线设备\"\"\"
    manager = get_heartbeat_manager()
    offline_devices = manager.check_offline_devices()
    
    if offline_devices:
        print(f"⚠️ 发现 {len(offline_devices)} 个离线设备:")
        for device_id in offline_devices:
            print(f"   - {device_id}")

@app.on_event("startup")
async def start_scheduler():
    # 每分钟检查一次离线设备
    scheduler.add_job(
        check_offline_devices_task,
        'interval',
        minutes=1,
        id='check_offline_devices'
    )
    scheduler.start()
    print("✅ 离线检测定时任务已启动")

@app.on_event("shutdown")
async def shutdown_scheduler():
    scheduler.shutdown()
    print("✅ 离线检测定时任务已停止")
"""


# ==================== AI智能体使用示例 ====================

"""
AI智能体可以通过心跳API监控设备状态：

示例对话1：
User: "哪些设备离线了？"
AI:
  1. 调用 GET /api/v1/devices/heartbeat/statistics
  2. 获取离线设备数量
  3. 调用 GET /api/v1/devices?status=offline
  4. 列出离线设备列表

示例对话2：
User: "检查device-xxx的心跳状态"
AI:
  1. 调用 GET /api/v1/devices/device-xxx/heartbeat
  2. 展示设备状态、最后上报时间、离线时长

示例对话3：
User: "手动检查所有设备的在线状态"
AI:
  1. 调用 POST /api/v1/devices/heartbeat/check-offline
  2. 汇报检测结果和离线设备列表
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
