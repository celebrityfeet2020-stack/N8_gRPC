# N8 Control Center - 设备控制中心

**版本**: v2.0.1-fixed  
**状态**: 生产就绪  
**作者**: Manus AI

---

## 📖 项目简介

N8控制中心是一个企业级分布式设备管理平台，提供：

- ✅ **集中管理**：统一界面管理Mac、Windows、Linux等多平台设备
- ✅ **实时监控**：实时查看设备状态（CPU/内存/磁盘）
- ✅ **远程控制**：安全地远程执行Shell命令
- ✅ **高可用性**：容器化部署、自动重启、健康检查
- ✅ **安全可控**：三层认证、细粒度权限、完整审计

---

## 🏗️ 系统架构

### 核心组件

| 组件 | 技术栈 | 端口 | 职责 |
|------|--------|------|------|
| **Web前端** | React + TypeScript + Tailwind | 14031 | 用户界面 |
| **REST API** | FastAPI + Uvicorn | 14032 | 业务逻辑与认证 |
| **gRPC Server** | Python + gRPC | 14033 | 设备通信 |
| **数据库** | PostgreSQL 15 | 14034 | 数据持久化 |
| **Agent** | Python + gRPC | - | 设备代理程序 |

### 技术栈

**前端**：React 18 + TypeScript + Tailwind CSS  
**后端**：Python 3.11 + FastAPI + gRPC + SQLAlchemy  
**数据库**：PostgreSQL 15  
**容器化**：Docker + Docker Compose  
**CI/CD**：GitHub Actions + Docker Hub

---

## 🚀 快速开始

### 1. 部署控制中心（D5服务器）

```bash
# 克隆仓库
git clone https://github.com/celebrityfeet2020-stack/n8-control-center.git
cd n8-control-center

# 启动服务
docker-compose up -d

# 查看状态
docker-compose ps

# 访问前端
open http://localhost:14031
```

### 2. 安装Agent（设备端）

**Linux**:
```bash
# 下载安装脚本
wget https://files.manuscdn.com/.../install.sh
chmod +x install.sh

# 安装
sudo bash install.sh
```

**macOS**:
```bash
# 下载安装脚本
curl -O https://files.manuscdn.com/.../install.sh
chmod +x install.sh

# 安装
sudo bash install.sh
```

**Windows**:
```powershell
# 下载安装脚本
Invoke-WebRequest -Uri "https://files.manuscdn.com/.../install.ps1" -OutFile "install.ps1"

# 安装
.\install.ps1
```

---

## 📦 Docker镜像

所有镜像已自动构建并推送到Docker Hub：

```bash
# 拉取镜像
docker pull junpeng999/n8-rest-api:latest-fixed
docker pull junpeng999/n8-grpc-server:latest-fixed
docker pull junpeng999/n8-db-init:latest-fixed
docker pull junpeng999/n8-web:latest-fixed
```

---

## 🔧 配置

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| DATABASE_URL | postgresql://... | 数据库连接 |
| AGENT_PSK | n8-super-secret-key-2024 | Agent预共享密钥 |
| GRPC_PORT | 50051 | gRPC端口 |
| HEARTBEAT_INTERVAL | 30 | 心跳间隔（秒） |
| DEVICE_TIMEOUT | 120 | 设备超时（秒） |

### 端口映射

| 服务 | 容器端口 | 主机端口 | 协议 |
|------|----------|----------|------|
| Web前端 | 80 | 14031 | HTTP |
| REST API | 8080 | 14032 | HTTP |
| gRPC Server | 50051 | 14033 | gRPC |
| PostgreSQL | 5432 | 14034 | SQL |

---

## 📚 文档

- [完整部署指南](docs/N8_Complete_Deployment_Guide.md)
- [API文档](docs/API.md)
- [Agent开发指南](docs/Agent.md)
- [故障排查](docs/Troubleshooting.md)

---

## 🔒 安全特性

- ✅ **三层认证**：PSK + Token + API Key
- ✅ **权限控制**：4种用户角色 + 3种设备权限
- ✅ **审计日志**：完整的操作记录
- ✅ **日志轮转**：防止日志爆盘（10MB×4个备份）
- ✅ **资源限制**：命令超时、输出限制

---

## 🎯 关键改进（v2.0.1-fixed）

### REST API修复

- ✅ 修复metadata字段验证失败问题
- ✅ 添加Field别名映射
- ✅ 手动构建API响应

### Agent修复

- ✅ 日志轮转（RotatingFileHandler）
- ✅ 心跳间隔从5秒改为30秒
- ✅ 指数退避重试策略
- ✅ 命令输出限制10000字符
- ✅ 命令超时5分钟

---

## 📊 监控

### 查看日志

```bash
# 控制中心
docker-compose logs -f rest-api
docker-compose logs -f grpc-server

# Agent
sudo tail -f /var/log/n8-agent.log
```

### 资源监控

```bash
# 控制中心
docker stats

# Agent
ps aux | grep n8-agent
top -p $(pgrep -f n8-agent)
```

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

## 📄 许可证

MIT License

---

## 📞 技术支持

如有任何问题，请：
1. 查看[完整部署指南](docs/N8_Complete_Deployment_Guide.md)
2. 检查[故障排查文档](docs/Troubleshooting.md)
3. 提交Issue到GitHub

---

**当前状态**：
- ✅ 代码已修复
- ✅ CI/CD已配置
- ✅ 文档已完善
- 🚀 生产就绪
