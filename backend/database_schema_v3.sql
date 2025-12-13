-- N8枢纽控制中心 - 数据库Schema v3.0
-- 创建时间: 2025-12-12
-- 说明: 实现设备和账号分离，支持三种API类型，72小时会话，完整日志系统

-- ============================================
-- 1. 删除旧表（如果存在）
-- ============================================

DROP TABLE IF EXISTS device_metrics CASCADE;
DROP TABLE IF EXISTS command_logs CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS devices CASCADE;

-- ============================================
-- 2. 创建核心表
-- ============================================

-- 2.1 设备表（被控设备）
CREATE TABLE devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) UNIQUE NOT NULL,  -- 设备唯一ID（优先使用内网IP，如192.168.9.125）
    device_name VARCHAR(100),                 -- 设备名称（如"M3"、"D5"、"VPS1"）
    device_type VARCHAR(50) DEFAULT 'unknown', -- 设备类型（windows/linux/macos）
    status VARCHAR(20) DEFAULT 'offline',     -- 设备状态（online/offline）
    last_seen TIMESTAMP,                      -- 最后心跳时间
    ip_address VARCHAR(50),                   -- 内网IP地址
    hostname VARCHAR(100),                    -- 主机名
    os_info TEXT,                             -- 操作系统信息（JSON格式）
    hardware_info TEXT,                       -- 硬件信息（JSON格式）
    agent_version VARCHAR(50),                -- Agent版本号
    metadata TEXT,                            -- 其他元数据（JSON格式）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2.2 API密钥表（控制账号）
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    api_key VARCHAR(64) UNIQUE NOT NULL,      -- API Key（SHA256生成）
    api_name VARCHAR(100) NOT NULL,           -- API名称（如"Manus主控API"、"小李"）
    api_type VARCHAR(20) NOT NULL,            -- API类型（web/external/internal）
    hashed_secret VARCHAR(255) NOT NULL,      -- 密钥哈希值（bcrypt）
    permissions TEXT,                         -- 权限列表（JSON格式，未来扩展）
    is_active BOOLEAN DEFAULT TRUE,           -- 是否激活
    expires_at TIMESTAMP,                     -- 过期时间（NULL表示永不过期）
    last_used_at TIMESTAMP,                   -- 最后使用时间
    created_by VARCHAR(100),                  -- 创建者
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2.3 会话表（Session管理）
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    session_token VARCHAR(64) UNIQUE NOT NULL, -- Session Token（UUID）
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE CASCADE,
    user_agent TEXT,                           -- 用户代理
    ip_address VARCHAR(50),                    -- 登录IP
    expires_at TIMESTAMP NOT NULL,             -- 过期时间（72小时）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2.4 命令执行日志表
CREATE TABLE command_logs (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) REFERENCES devices(device_id) ON DELETE CASCADE,
    command_type VARCHAR(50) NOT NULL,         -- 命令类型（shell/file_upload/file_download/process_kill等）
    command_content TEXT NOT NULL,             -- 命令内容
    command_result TEXT,                       -- 命令结果
    status VARCHAR(20) DEFAULT 'pending',      -- 状态（pending/success/failed）
    executed_by VARCHAR(100),                  -- 执行者（API Key名称）
    execution_time FLOAT,                      -- 执行时间（秒）
    error_message TEXT,                        -- 错误信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 2.5 设备性能指标表
CREATE TABLE device_metrics (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) REFERENCES devices(device_id) ON DELETE CASCADE,
    cpu_usage FLOAT,                           -- CPU使用率（%）
    memory_usage FLOAT,                        -- 内存使用率（%）
    disk_usage FLOAT,                          -- 硬盘使用率（%）
    gpu_usage FLOAT,                           -- GPU使用率（%）
    network_rx_bytes BIGINT,                   -- 网络接收字节数
    network_tx_bytes BIGINT,                   -- 网络发送字节数
    process_count INTEGER,                     -- 进程数量
    uptime_seconds BIGINT,                     -- 运行时间（秒）
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 3. 创建索引（优化查询性能）
-- ============================================

-- 设备表索引
CREATE INDEX idx_devices_device_id ON devices(device_id);
CREATE INDEX idx_devices_status ON devices(status);
CREATE INDEX idx_devices_last_seen ON devices(last_seen);

-- API密钥表索引
CREATE INDEX idx_api_keys_api_key ON api_keys(api_key);
CREATE INDEX idx_api_keys_api_type ON api_keys(api_type);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);

-- 会话表索引
CREATE INDEX idx_sessions_session_token ON sessions(session_token);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_sessions_api_key_id ON sessions(api_key_id);

-- 命令日志表索引
CREATE INDEX idx_command_logs_device_id ON command_logs(device_id);
CREATE INDEX idx_command_logs_created_at ON command_logs(created_at);
CREATE INDEX idx_command_logs_status ON command_logs(status);
CREATE INDEX idx_command_logs_command_type ON command_logs(command_type);

-- 设备性能指标表索引
CREATE INDEX idx_device_metrics_device_id ON device_metrics(device_id);
CREATE INDEX idx_device_metrics_recorded_at ON device_metrics(recorded_at);

-- ============================================
-- 4. 创建触发器（自动更新updated_at）
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_keys_updated_at
    BEFORE UPDATE ON api_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 5. 插入初始数据
-- ============================================

-- 5.1 插入初始API Key（需要在应用层生成实际的哈希值）
-- 注意：这里的hashed_secret是占位符，实际部署时需要替换为真实的bcrypt哈希值

INSERT INTO api_keys (api_key, api_name, api_type, hashed_secret, permissions, created_by) VALUES
-- Manus主控API（external类型，从VPS1进入）
('manus_master_api_key_2024_v1', 'Manus主控API', 'external', '$2b$12$placeholder_hash_1', '["*"]', 'system'),

-- Web管理员API（web类型，人类通过浏览器使用）
('web_admin_api_key_2024_v1', 'Web管理员', 'web', '$2b$12$placeholder_hash_2', '["*"]', 'system'),

-- 内网AI智能体API（internal类型，局域网内AI使用）
('internal_ai_api_key_2024_v1', '内网AI智能体', 'internal', '$2b$12$placeholder_hash_3', '["*"]', 'system');

-- 5.2 插入初始设备（示例）
INSERT INTO devices (device_id, device_name, device_type, status, ip_address, hostname) VALUES
('192.168.9.113', 'D5', 'linux', 'offline', '192.168.9.113', 'Double5090'),
('192.168.9.125', 'M3', 'linux', 'offline', '192.168.9.125', 'kori-M3'),
('192.168.9.92', 'C1650-1', 'linux', 'offline', '192.168.9.92', 'c1650-1'),
('43.160.207.239', 'VPS1', 'linux', 'offline', '43.160.207.239', 'VPS1-Singapore');

-- ============================================
-- 6. 授权（确保n8_user有权限）
-- ============================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO n8_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO n8_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO n8_user;

-- ============================================
-- 完成！
-- ============================================
