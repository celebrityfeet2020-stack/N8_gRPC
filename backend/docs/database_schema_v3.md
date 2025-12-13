# N8控制中心 - 数据库架构设计 v3.0

## 设计理念

**核心分离**：被控设备（Devices）与控制账号（API Keys）完全独立

**三种API类型**：
1. `web` - Web视窗控制（人类用户）
2. `external` - 外网API（VPS1，Manus使用）
3. `internal` - 内网AI API（局域网AI智能体）

---

## 表结构设计

### 1. devices（被控设备表）

**用途**：记录所有安装了Agent的设备

```sql
CREATE TABLE devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) UNIQUE NOT NULL,          -- 设备唯一ID（内网IP或自动生成）
    device_name VARCHAR(255),                         -- 用户自定义设备名称（如"M3"、"VPS1"）
    local_ip VARCHAR(50),                             -- 设备内网IP（如192.168.9.125）
    hostname VARCHAR(255),                            -- 设备主机名
    os_type VARCHAR(50),                              -- 操作系统类型（Linux/Windows/macOS）
    os_version VARCHAR(100),                          -- 操作系统版本
    cpu_model VARCHAR(255),                           -- CPU型号
    cpu_cores INTEGER,                                -- CPU核心数
    memory_total BIGINT,                              -- 总内存（字节）
    disk_total BIGINT,                                -- 总磁盘空间（字节）
    agent_version VARCHAR(50),                        -- Agent版本号
    status VARCHAR(20) DEFAULT 'offline',             -- 设备状态（online/offline/error）
    last_heartbeat TIMESTAMP,                         -- 最后心跳时间
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,-- 注册时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,   -- 更新时间
    metadata JSONB                                    -- 扩展元数据（JSON格式）
);

CREATE INDEX idx_devices_device_id ON devices(device_id);
CREATE INDEX idx_devices_status ON devices(status);
CREATE INDEX idx_devices_local_ip ON devices(local_ip);
```

**字段说明**：
- `device_id`: 唯一标识，优先使用内网IP（如`192.168.9.125`），无法获取则用hostname
- `device_name`: 用户在Web界面自定义的名称，方便识别（如"M3"、"D5"、"VPS1"）
- `status`: 根据心跳时间自动更新（超过2分钟无心跳则offline）
- `metadata`: 存储额外信息（如GPU信息、网络接口等）

---

### 2. api_keys（控制账号表）

**用途**：管理所有API访问凭证

```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    key_id VARCHAR(64) UNIQUE NOT NULL,               -- API Key ID（如"ak_manus_primary"）
    key_secret VARCHAR(128) UNIQUE NOT NULL,          -- API Key Secret（加密存储）
    key_name VARCHAR(255) NOT NULL,                   -- API名称（如"Manus主账号"、"小李"）
    key_type VARCHAR(20) NOT NULL,                    -- API类型（web/external/internal）
    permissions JSONB DEFAULT '[]',                   -- 权限列表（JSON数组，未来扩展）
    is_active BOOLEAN DEFAULT true,                   -- 是否启用
    expires_at TIMESTAMP,                             -- 过期时间（NULL表示永不过期）
    created_by VARCHAR(255),                          -- 创建者
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,   -- 创建时间
    last_used_at TIMESTAMP,                           -- 最后使用时间
    usage_count INTEGER DEFAULT 0,                    -- 使用次数
    metadata JSONB                                    -- 扩展元数据
);

CREATE INDEX idx_api_keys_key_id ON api_keys(key_id);
CREATE INDEX idx_api_keys_key_type ON api_keys(key_type);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
```

**字段说明**：
- `key_id`: 公开的Key ID（如`ak_manus_primary`）
- `key_secret`: 私密的Secret（使用bcrypt加密，类似密码）
- `key_type`: 区分三种API类型
  - `web`: Web视窗控制（人类用户）
  - `external`: 外网API（VPS1，Manus）
  - `internal`: 内网AI API（M3、D5上的AI智能体）
- `permissions`: 未来扩展权限控制（如只读、可执行命令、可管理设备等）

---

### 3. sessions（会话表）

**用途**：管理API Key的登录会话（48小时有效期）

```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    session_token VARCHAR(128) UNIQUE NOT NULL,       -- 会话Token（JWT或随机字符串）
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE CASCADE,
    device_id VARCHAR(255),                           -- 关联的设备ID（可选）
    ip_address VARCHAR(50),                           -- 登录IP地址
    user_agent TEXT,                                  -- 用户代理（浏览器/客户端信息）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,   -- 创建时间
    expires_at TIMESTAMP NOT NULL,                    -- 过期时间（创建时间+48小时）
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 最后活动时间
    is_active BOOLEAN DEFAULT true                    -- 是否有效
);

CREATE INDEX idx_sessions_session_token ON sessions(session_token);
CREATE INDEX idx_sessions_api_key_id ON sessions(api_key_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
```

**字段说明**：
- `session_token`: 登录后返回的Token，后续请求携带此Token
- `expires_at`: 48小时有效期（可配置）
- `last_activity_at`: 每次请求更新，用于判断活跃度

---

### 4. command_logs（命令日志表）

**用途**：记录所有通过API执行的命令

```sql
CREATE TABLE command_logs (
    id SERIAL PRIMARY KEY,
    command_id VARCHAR(64) UNIQUE NOT NULL,           -- 命令唯一ID
    device_id VARCHAR(255) NOT NULL,                  -- 目标设备ID
    api_key_id INTEGER REFERENCES api_keys(id),       -- 执行者API Key
    session_id INTEGER REFERENCES sessions(id),       -- 关联会话
    command_type VARCHAR(50) NOT NULL,                -- 命令类型（shell/file_upload/file_download等）
    command_content TEXT NOT NULL,                    -- 命令内容
    command_status VARCHAR(20) DEFAULT 'pending',     -- 状态（pending/running/completed/failed）
    result TEXT,                                      -- 执行结果
    exit_code INTEGER,                                -- 退出码
    started_at TIMESTAMP,                             -- 开始执行时间
    completed_at TIMESTAMP,                           -- 完成时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,   -- 创建时间
    metadata JSONB                                    -- 扩展元数据
);

CREATE INDEX idx_command_logs_device_id ON command_logs(device_id);
CREATE INDEX idx_command_logs_api_key_id ON command_logs(api_key_id);
CREATE INDEX idx_command_logs_command_status ON command_logs(command_status);
CREATE INDEX idx_command_logs_created_at ON command_logs(created_at);
```

**字段说明**：
- `command_type`: 支持多种命令类型（shell、文件传输、系统信息查询等）
- `command_status`: 命令执行状态流转
- `result`: 存储命令输出结果

---

### 5. device_metrics（设备指标表）

**用途**：记录设备性能指标历史数据

```sql
CREATE TABLE device_metrics (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,                  -- 设备ID
    cpu_usage FLOAT,                                  -- CPU使用率（%）
    memory_usage FLOAT,                               -- 内存使用率（%）
    disk_usage FLOAT,                                 -- 磁盘使用率（%）
    network_rx_bytes BIGINT,                          -- 网络接收字节数
    network_tx_bytes BIGINT,                          -- 网络发送字节数
    load_average FLOAT,                               -- 系统负载
    process_count INTEGER,                            -- 进程数量
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 记录时间
    metadata JSONB                                    -- 扩展指标
);

CREATE INDEX idx_device_metrics_device_id ON device_metrics(device_id);
CREATE INDEX idx_device_metrics_recorded_at ON device_metrics(recorded_at);
```

**字段说明**：
- 每次心跳时记录一次设备指标
- 用于前端展示设备性能趋势图

---

## 数据关系图

```
┌─────────────────┐
│   api_keys      │
│  (控制账号)      │
└────────┬────────┘
         │ 1:N
         ▼
┌─────────────────┐        ┌─────────────────┐
│   sessions      │        │   devices       │
│   (会话)        │        │  (被控设备)      │
└────────┬────────┘        └────────┬────────┘
         │                          │
         │ N:1                      │ 1:N
         │                          │
         └──────────┬───────────────┘
                    ▼
         ┌─────────────────┐
         │ command_logs    │
         │  (命令日志)      │
         └─────────────────┘
                    │
                    │ 1:N
                    ▼
         ┌─────────────────┐
         │ device_metrics  │
         │  (设备指标)      │
         └─────────────────┘
```

---

## 初始化数据

### 1. 创建超级管理员API Key

```sql
INSERT INTO api_keys (key_id, key_secret, key_name, key_type, permissions, created_by)
VALUES (
    'ak_admin_root',
    -- 实际部署时用bcrypt加密
    '$2b$12$...',  -- 对应明文: 'N8-Super-Admin-Key-2024'
    'N8超级管理员',
    'web',
    '["*"]',  -- 全权限
    'system'
);
```

### 2. 创建Manus专用API Key

```sql
INSERT INTO api_keys (key_id, key_secret, key_name, key_type, permissions, created_by)
VALUES (
    'ak_manus_primary',
    '$2b$12$...',  -- 对应明文: 'Manus-Primary-Key-2024'
    'Manus主账号',
    'external',
    '["*"]',
    'admin'
);
```

---

## 迁移策略

### 从v2.0迁移到v3.0

**步骤**：
1. 备份现有数据库
2. 创建新表结构
3. 迁移现有设备数据到`devices`表
4. 创建默认API Keys
5. 删除旧表（可选）

**迁移SQL**：
```sql
-- 迁移设备数据
INSERT INTO devices (device_id, device_name, hostname, status, last_heartbeat, registered_at)
SELECT 
    device_id,
    device_id as device_name,  -- 初始名称与ID相同
    hostname,
    status,
    last_seen as last_heartbeat,
    registered_at
FROM old_devices_table;

-- 更新设备名称（根据内网IP）
UPDATE devices 
SET device_name = 'VPS1' 
WHERE device_id LIKE '%43.160.207.239%' OR hostname = 'VM-0-16-ubuntu';

UPDATE devices 
SET device_name = 'D5' 
WHERE local_ip = '192.168.9.113' OR hostname LIKE '%Double5090%';

UPDATE devices 
SET device_name = 'M3' 
WHERE local_ip = '192.168.9.125';
```

---

## 性能优化

### 1. 索引策略
- 所有外键字段建立索引
- 高频查询字段建立索引（device_id, status, session_token等）
- 时间字段建立索引（用于范围查询）

### 2. 数据清理
- `sessions`: 定期清理过期会话（保留7天）
- `command_logs`: 定期归档旧日志（保留30天）
- `device_metrics`: 定期聚合历史数据（小时/天级别）

### 3. 分区策略（未来扩展）
- `command_logs`: 按月分区
- `device_metrics`: 按周分区

---

## 安全考虑

### 1. 敏感数据加密
- `api_keys.key_secret`: 使用bcrypt加密（不可逆）
- `sessions.session_token`: 使用随机字符串+签名

### 2. 访问控制
- 所有API请求必须携带有效的session_token
- session_token与api_key_id绑定，防止token泄露

### 3. 审计日志
- 所有命令执行记录到`command_logs`
- 记录API Key使用次数和最后使用时间

---

## API设计示例

### 1. 设备管理API

```
GET    /api/devices              - 获取设备列表
GET    /api/devices/{device_id}  - 获取设备详情
PUT    /api/devices/{device_id}  - 更新设备信息（如重命名）
DELETE /api/devices/{device_id}  - 删除设备（取消注册）
GET    /api/devices/{device_id}/metrics - 获取设备指标
POST   /api/devices/{device_id}/command - 执行命令
```

### 2. API Key管理API

```
GET    /api/keys                 - 获取API Key列表
POST   /api/keys                 - 创建新API Key
GET    /api/keys/{key_id}        - 获取API Key详情
PUT    /api/keys/{key_id}        - 更新API Key（如重命名、禁用）
DELETE /api/keys/{key_id}        - 删除API Key
POST   /api/keys/{key_id}/regenerate - 重新生成Secret
```

### 3. 认证API

```
POST   /api/auth/login           - 使用API Key登录（返回session_token）
POST   /api/auth/logout          - 登出（销毁session）
GET    /api/auth/session         - 获取当前会话信息
POST   /api/auth/refresh         - 刷新会话（延长48小时）
```

---

## 总结

**v3.0架构优势**：
1. ✅ 清晰分离"被控设备"和"控制账号"
2. ✅ 支持三种API类型（web/external/internal）
3. ✅ 设备自动注册（使用内网IP作为ID）
4. ✅ 灵活的权限管理（未来扩展）
5. ✅ 完整的审计日志
6. ✅ 48小时会话有效期
7. ✅ 可扩展的元数据存储（JSONB）

**下一步**：
- 编写数据库迁移脚本
- 更新后端API代码
- 更新gRPC Server代码
- 更新Agent代码
- 重构前端UI
