"""
N8 gRPC Control Center - gRPC Server Implementation
"""

import grpc
import hashlib
import secrets
import time
import json
import logging
from concurrent import futures
from datetime import datetime, timedelta
from typing import Optional, Iterator

import device_control_pb2 as pb2
import device_control_pb2_grpc as pb2_grpc

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base, Device, Command, AuditLog


# ============================================
# 配置
# ============================================

class ControlCenterConfig:
    """控制中心配置"""
    def __init__(self):
        import os
        self.database_url = os.getenv("DATABASE_URL", "postgresql://n8_user:password@postgres:5432/n8_control")
        self.psk = os.getenv("AGENT_PSK", "default-secret-key")
        self.grpc_port = int(os.getenv("GRPC_PORT", "50051"))
        self.heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
        self.device_timeout = int(os.getenv("DEVICE_TIMEOUT", "120"))  # 2分钟无心跳则离线


# ============================================
# 数据库管理
# ============================================

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
    def init_db(self):
        """初始化数据库"""
        Base.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()


# ============================================
# gRPC服务实现
# ============================================

class ControlCenterService(pb2_grpc.ControlCenterServicer):
    """控制中心gRPC服务"""
    
    def __init__(self, config: ControlCenterConfig, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.logger = logging.getLogger("ControlCenter")
        
    def _verify_psk(self, psk: str) -> bool:
        """验证预共享密钥"""
        return psk == self.config.psk
    
    def _generate_token(self) -> str:
        """生成认证令牌"""
        return secrets.token_urlsafe(32)
    
    def _hash_psk(self, psk: str) -> str:
        """哈希PSK"""
        return hashlib.sha256(psk.encode()).hexdigest()
    
    def _verify_token(self, device_id: str, token: str, session: Session) -> bool:
        """验证设备令牌"""
        device = session.query(Device).filter_by(device_id=device_id, token=token).first()
        return device is not None
    
    def Register(self, request: pb2.RegisterRequest, context) -> pb2.RegisterResponse:
        """设备注册"""
        try:
            # 验证PSK
            if not self._verify_psk(request.psk):
                self.logger.warning(f"Invalid PSK from device {request.device_id}")
                return pb2.RegisterResponse(
                    success=False,
                    message="Invalid PSK",
                    token="",
                    heartbeat_interval=0
                )
            
            session = self.db_manager.get_session()
            
            try:
                # 查找或创建设备
                device = session.query(Device).filter_by(device_id=request.device_id).first()
                
                if device:
                    # 更新现有设备
                    device.hostname = request.hostname
                    device.os_type = request.os_type
                    device.os_version = request.os_version
                    device.agent_version = request.agent_version
                    device.metadata = dict(request.metadata)
                    device.status = "online"
                    device.last_seen_at = datetime.now()
                    self.logger.info(f"Device {request.device_id} re-registered")
                else:
                    # 创建新设备
                    token = self._generate_token()
                    device = Device(
                        device_id=request.device_id,
                        hostname=request.hostname,
                        os_type=request.os_type,
                        os_version=request.os_version,
                        agent_version=request.agent_version,
                        token=token,
                        psk_hash=self._hash_psk(request.psk),
                        metadata=dict(request.metadata),
                        status="online"
                    )
                    session.add(device)
                    self.logger.info(f"New device registered: {request.device_id}")
                
                # 记录审计日志
                audit = AuditLog(
                    device_id=request.device_id,
                    action="register",
                    details={
                        "hostname": request.hostname,
                        "os_type": request.os_type,
                        "agent_version": request.agent_version
                    }
                )
                session.add(audit)
                
                session.commit()
                
                return pb2.RegisterResponse(
                    success=True,
                    message="Registration successful",
                    token=device.token,
                    heartbeat_interval=self.config.heartbeat_interval
                )
            
            finally:
                session.close()
        
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return pb2.RegisterResponse(
                success=False,
                message=f"Internal error: {str(e)}",
                token="",
                heartbeat_interval=0
            )
    
    def Heartbeat(self, request: pb2.HeartbeatRequest, context) -> pb2.HeartbeatResponse:
        """心跳"""
        session = self.db_manager.get_session()
        
        try:
            # 验证令牌
            if not self._verify_token(request.device_id, request.token, session):
                return pb2.HeartbeatResponse(
                    success=False,
                    message="Invalid token"
                )
            
            # 更新设备状态
            device = session.query(Device).filter_by(device_id=request.device_id).first()
            if device:
                device.status = "online"
                device.last_seen_at = datetime.now()
                device.cpu_usage = request.status.cpu_usage
                device.memory_usage = request.status.memory_usage
                device.disk_usage = request.status.disk_usage
                device.uptime = request.status.uptime
                device.running_services = list(request.status.running_services)
                
                session.commit()
                
                self.logger.debug(f"Heartbeat from {request.device_id}")
                
                return pb2.HeartbeatResponse(
                    success=True,
                    message="OK"
                )
            else:
                return pb2.HeartbeatResponse(
                    success=False,
                    message="Device not found"
                )
        
        except Exception as e:
            self.logger.error(f"Heartbeat error: {e}")
            return pb2.HeartbeatResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
        
        finally:
            session.close()
    
    def PullCommands(self, request: pb2.PullCommandsRequest, context) -> Iterator[pb2.Command]:
        """拉取命令（流式）"""
        session = self.db_manager.get_session()
        
        try:
            # 验证令牌
            if not self._verify_token(request.device_id, request.token, session):
                self.logger.warning(f"Invalid token from {request.device_id}")
                return
            
            self.logger.info(f"Device {request.device_id} connected for command pull")
            
            # 长连接循环
            while context.is_active():
                try:
                    # 查询待执行的命令
                    commands = session.query(Command).filter_by(
                        device_id=request.device_id,
                        status="pending"
                    ).order_by(Command.created_at).limit(10).all()
                    
                    for cmd in commands:
                        # 标记为运行中
                        cmd.status = "running"
                        session.commit()
                        
                        # 发送命令
                        yield pb2.Command(
                            command_id=cmd.command_id,
                            command_type=cmd.command_type,
                            payload=cmd.payload,
                            created_at=int(cmd.created_at.timestamp()),
                            timeout=cmd.timeout
                        )
                        
                        self.logger.info(f"Sent command {cmd.command_id} to {request.device_id}")
                    
                    # 刷新会话
                    session.expire_all()
                    
                    # 等待5秒再查询
                    time.sleep(5)
                
                except Exception as e:
                    self.logger.error(f"Error in command pull loop: {e}")
                    break
        
        finally:
            session.close()
            self.logger.info(f"Device {request.device_id} disconnected from command pull")
    
    def ReportResult(self, request: pb2.CommandResult, context) -> pb2.ReportResponse:
        """上报命令执行结果"""
        session = self.db_manager.get_session()
        
        try:
            # 验证令牌
            if not self._verify_token(request.device_id, request.token, session):
                return pb2.ReportResponse(
                    success=False,
                    message="Invalid token"
                )
            
            # 更新命令状态
            command = session.query(Command).filter_by(command_id=request.command_id).first()
            
            if command:
                command.status = "completed" if request.success else "failed"
                command.success = request.success
                command.stdout = request.stdout
                command.stderr = request.stderr
                command.exit_code = request.exit_code
                command.executed_at = datetime.fromtimestamp(request.executed_at)
                command.duration_ms = request.duration_ms
                
                # 记录审计日志
                audit = AuditLog(
                    device_id=request.device_id,
                    action="command_result",
                    details={
                        "command_id": request.command_id,
                        "success": request.success,
                        "exit_code": request.exit_code,
                        "duration_ms": request.duration_ms
                    }
                )
                session.add(audit)
                
                session.commit()
                
                self.logger.info(f"Command {request.command_id} result received: {'success' if request.success else 'failed'}")
                
                return pb2.ReportResponse(
                    success=True,
                    message="Result recorded"
                )
            else:
                return pb2.ReportResponse(
                    success=False,
                    message="Command not found"
                )
        
        except Exception as e:
            self.logger.error(f"Report result error: {e}")
            return pb2.ReportResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
        
        finally:
            session.close()
    
    def StreamLogs(self, request_iterator, context) -> pb2.StreamLogsResponse:
        """流式接收日志"""
        # TODO: 实现日志流式上传
        return pb2.StreamLogsResponse(
            success=True,
            message="Not implemented yet",
            bytes_received=0
        )


# ============================================
# 设备状态监控
# ============================================

class DeviceMonitor:
    """设备状态监控（标记离线设备）"""
    
    def __init__(self, config: ControlCenterConfig, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.logger = logging.getLogger("DeviceMonitor")
    
    def run(self):
        """运行监控循环"""
        import threading
        
        def monitor_loop():
            while True:
                try:
                    session = self.db_manager.get_session()
                    
                    try:
                        # 查找超时设备
                        timeout_threshold = datetime.now() - timedelta(seconds=self.config.device_timeout)
                        
                        offline_devices = session.query(Device).filter(
                            Device.status == "online",
                            Device.last_seen_at < timeout_threshold
                        ).all()
                        
                        for device in offline_devices:
                            device.status = "offline"
                            self.logger.warning(f"Device {device.device_id} marked as offline")
                        
                        if offline_devices:
                            session.commit()
                    
                    finally:
                        session.close()
                
                except Exception as e:
                    self.logger.error(f"Monitor error: {e}")
                
                time.sleep(30)  # 每30秒检查一次
        
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        self.logger.info("Device monitor started")


# ============================================
# 主服务器
# ============================================

def serve():
    """启动gRPC服务器"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("Main")
    
    # 加载配置
    config = ControlCenterConfig()
    logger.info(f"Database URL: {config.database_url}")
    logger.info(f"gRPC Port: {config.grpc_port}")
    
    # 初始化数据库
    db_manager = DatabaseManager(config.database_url)
    db_manager.init_db()
    logger.info("Database initialized")
    
    # 启动设备监控
    monitor = DeviceMonitor(config, db_manager)
    monitor.run()
    
    # 创建gRPC服务器
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_ControlCenterServicer_to_server(
        ControlCenterService(config, db_manager),
        server
    )
    
    # 监听端口
    server.add_insecure_port(f'[::]:{config.grpc_port}')
    server.start()
    
    logger.info(f"gRPC Control Center started on port {config.grpc_port}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.stop(0)


if __name__ == "__main__":
    serve()
