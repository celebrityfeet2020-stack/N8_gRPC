-- N8控制中心数据库迁移脚本 v2.0 → v3.0
-- 执行前请务必备份数据库！

-- ============================================
-- 第一步：创建新表结构
-- ============================================

-- 1. 被控设备表
CREATE TABLE IF NOT EXISTS devices_v3 (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) UNIQUE NOT NULL,
    device_name VARCHAR(255),
    local_ip VARCHAR(50),
    hostname VARCHAR(255),
    os_type VARCHAR(50),
    os_version VARCHAR(100),
    cpu_model VARCHAR(255),
    cpu_cores INTEGER,
    memory_total BIGINT,
    disk_total BIGINT,
    agent_version VARCHAR(50),
    status VARCHAR(20) DEFAULT 'offline',
    last_heartbeat TIMESTAMP,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_devices_v3_device_id ON devices_v3(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_v3_status ON devices_v3(status);
CREATE INDEX IF NOT EXISTS idx_devices_v3_local_ip ON devices_v3(local_ip);

-- 2. 控制账号表（API Keys）
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_id VARCHAR(64) UNIQUE NOT NULL,
    key_secret VARCHAR(128) UNIQUE NOT NULL,
    key_name VARCHAR(255) NOT NULL,
    key_type VARCHAR(20) NOT NULL CHECK (key_type IN ('web', 'external', 'internal')),
    permissions JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_id ON api_keys(key_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_type ON api_keys(key_type);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);

-- 3. 会话表
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_token VARCHAR(128) UNIQUE NOT NULL,
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE CASCADE,
    device_id VARCHAR(255),
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_sessions_session_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_api_key_id ON sessions(api_key_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- 4. 命令日志表
CREATE TABLE IF NOT EXISTS command_logs (
    id SERIAL PRIMARY KEY,
    command_id VARCHAR(64) UNIQUE NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    api_key_id INTEGER REFERENCES api_keys(id),
    session_id INTEGER REFERENCES sessions(id),
    command_type VARCHAR(50) NOT NULL,
    command_content TEXT NOT NULL,
    command_status VARCHAR(20) DEFAULT 'pending' CHECK (command_status IN ('pending', 'running', 'completed', 'failed', 'timeout')),
    result TEXT,
    exit_code INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_command_logs_device_id ON command_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_command_logs_api_key_id ON command_logs(api_key_id);
CREATE INDEX IF NOT EXISTS idx_command_logs_command_status ON command_logs(command_status);
CREATE INDEX IF NOT EXISTS idx_command_logs_created_at ON command_logs(created_at);

-- 5. 设备指标表
CREATE TABLE IF NOT EXISTS device_metrics (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    cpu_usage FLOAT,
    memory_usage FLOAT,
    disk_usage FLOAT,
    network_rx_bytes BIGINT,
    network_tx_bytes BIGINT,
    load_average FLOAT,
    process_count INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_device_metrics_device_id ON device_metrics(device_id);
CREATE INDEX IF NOT EXISTS idx_device_metrics_recorded_at ON device_metrics(recorded_at);

-- ============================================
-- 第二步：迁移现有数据（如果存在旧表）
-- ============================================

-- 迁移设备数据（从旧的devices表）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'devices') THEN
        INSERT INTO devices_v3 (device_id, device_name, hostname, status, last_heartbeat, registered_at, metadata)
        SELECT 
            device_id,
            COALESCE(device_name, device_id) as device_name,
            hostname,
            CASE 
                WHEN status = 'online' THEN 'online'
                WHEN status = 'offline' THEN 'offline'
                ELSE 'offline'
            END as status,
            last_seen as last_heartbeat,
            registered_at,
            metadata
        FROM devices
        ON CONFLICT (device_id) DO NOTHING;
        
        RAISE NOTICE '已迁移 % 个设备', (SELECT COUNT(*) FROM devices_v3);
    END IF;
END $$;

-- ============================================
-- 第三步：创建初始API Keys
-- ============================================

-- 超级管理员API Key（Web类型）
-- 注意：这里使用明文密码，实际部署时应该用bcrypt加密
INSERT INTO api_keys (key_id, key_secret, key_name, key_type, permissions, created_by, metadata)
VALUES (
    'ak_admin_root',
    'N8-Super-Admin-Key-2024-CHANGE-ME',  -- 请修改此密码！
    'N8超级管理员',
    'web',
    '["*"]'::jsonb,
    'system',
    '{"description": "系统默认超级管理员账号，拥有全部权限"}'::jsonb
) ON CONFLICT (key_id) DO NOTHING;

-- Manus专用API Key（外网类型）
INSERT INTO api_keys (key_id, key_secret, key_name, key_type, permissions, created_by, metadata)
VALUES (
    'ak_manus_primary',
    'Manus-Primary-Key-2024-CHANGE-ME',  -- 请修改此密码！
    'Manus主账号',
    'external',
    '["*"]'::jsonb,
    'admin',
    '{"description": "Manus AI专用外网访问账号"}'::jsonb
) ON CONFLICT (key_id) DO NOTHING;

-- 示例：内网AI API Key
INSERT INTO api_keys (key_id, key_secret, key_name, key_type, permissions, created_by, metadata)
VALUES (
    'ak_ai_m3',
    'M3-AI-Agent-Key-2024-CHANGE-ME',  -- 请修改此密码！
    'M3 AI智能体',
    'internal',
    '["device:read", "device:command"]'::jsonb,
    'admin',
    '{"description": "M3设备上运行的AI智能体专用账号"}'::jsonb
) ON CONFLICT (key_id) DO NOTHING;

-- ============================================
-- 第四步：更新设备名称（根据已知信息）
-- ============================================

-- 更新VPS1设备名称
UPDATE devices_v3 
SET device_name = 'VPS1',
    local_ip = '43.160.207.239',
    updated_at = CURRENT_TIMESTAMP
WHERE hostname = 'VM-0-16-ubuntu' OR device_id LIKE '%VM-0-16%';

-- 更新D5设备名称
UPDATE devices_v3 
SET device_name = 'D5',
    local_ip = '192.168.9.113',
    updated_at = CURRENT_TIMESTAMP
WHERE hostname LIKE '%Double5090%' OR device_id LIKE '%192.168.9.113%';

-- 更新M3设备名称
UPDATE devices_v3 
SET device_name = 'M3',
    local_ip = '192.168.9.125',
    updated_at = CURRENT_TIMESTAMP
WHERE device_id LIKE '%192.168.9.125%';

-- ============================================
-- 第五步：创建自动更新触发器
-- ============================================

-- 设备更新时间自动更新触发器
CREATE OR REPLACE FUNCTION update_devices_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_devices_updated_at ON devices_v3;
CREATE TRIGGER trigger_devices_updated_at
    BEFORE UPDATE ON devices_v3
    FOR EACH ROW
    EXECUTE FUNCTION update_devices_updated_at();

-- 会话最后活动时间自动更新触发器
CREATE OR REPLACE FUNCTION update_sessions_last_activity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_activity_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_sessions_last_activity ON sessions;
CREATE TRIGGER trigger_sessions_last_activity
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_sessions_last_activity();

-- ============================================
-- 第六步：创建视图（便于查询）
-- ============================================

-- 在线设备视图
CREATE OR REPLACE VIEW online_devices AS
SELECT 
    device_id,
    device_name,
    local_ip,
    hostname,
    os_type,
    cpu_cores,
    memory_total,
    agent_version,
    last_heartbeat,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_heartbeat)) as seconds_since_heartbeat
FROM devices_v3
WHERE status = 'online'
  AND last_heartbeat > CURRENT_TIMESTAMP - INTERVAL '2 minutes'
ORDER BY last_heartbeat DESC;

-- 活跃会话视图
CREATE OR REPLACE VIEW active_sessions AS
SELECT 
    s.session_token,
    s.ip_address,
    s.created_at,
    s.expires_at,
    s.last_activity_at,
    ak.key_id,
    ak.key_name,
    ak.key_type,
    EXTRACT(EPOCH FROM (s.expires_at - CURRENT_TIMESTAMP)) / 3600 as hours_until_expiry
FROM sessions s
JOIN api_keys ak ON s.api_key_id = ak.id
WHERE s.is_active = true
  AND s.expires_at > CURRENT_TIMESTAMP
ORDER BY s.last_activity_at DESC;

-- 最近命令日志视图
CREATE OR REPLACE VIEW recent_commands AS
SELECT 
    cl.command_id,
    cl.device_id,
    d.device_name,
    ak.key_name as executed_by,
    cl.command_type,
    cl.command_status,
    cl.created_at,
    cl.completed_at,
    EXTRACT(EPOCH FROM (cl.completed_at - cl.started_at)) as execution_seconds
FROM command_logs cl
LEFT JOIN devices_v3 d ON cl.device_id = d.device_id
LEFT JOIN api_keys ak ON cl.api_key_id = ak.id
ORDER BY cl.created_at DESC
LIMIT 100;

-- ============================================
-- 第七步：创建清理函数（定期执行）
-- ============================================

-- 清理过期会话
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM sessions
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 清理旧命令日志（保留30天）
CREATE OR REPLACE FUNCTION cleanup_old_command_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM command_logs
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 清理旧设备指标（保留7天）
CREATE OR REPLACE FUNCTION cleanup_old_device_metrics()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM device_metrics
    WHERE recorded_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 第八步：重命名表（如果需要保留旧表）
-- ============================================

-- 备份旧表
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'devices') THEN
        ALTER TABLE devices RENAME TO devices_backup_v2;
        RAISE NOTICE '旧devices表已重命名为devices_backup_v2';
    END IF;
END $$;

-- 将新表重命名为正式表名
ALTER TABLE devices_v3 RENAME TO devices;

-- 重建索引（使用新表名）
DROP INDEX IF EXISTS idx_devices_v3_device_id;
DROP INDEX IF EXISTS idx_devices_v3_status;
DROP INDEX IF EXISTS idx_devices_v3_local_ip;

CREATE INDEX idx_devices_device_id ON devices(device_id);
CREATE INDEX idx_devices_status ON devices(status);
CREATE INDEX idx_devices_local_ip ON devices(local_ip);

-- ============================================
-- 第九步：验证迁移结果
-- ============================================

-- 显示迁移统计信息
DO $$
DECLARE
    device_count INTEGER;
    api_key_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO device_count FROM devices;
    SELECT COUNT(*) INTO api_key_count FROM api_keys;
    
    RAISE NOTICE '===========================================';
    RAISE NOTICE '数据库迁移完成！';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '设备数量: %', device_count;
    RAISE NOTICE 'API Key数量: %', api_key_count;
    RAISE NOTICE '===========================================';
    RAISE NOTICE '请务必修改默认API Key密码！';
    RAISE NOTICE '===========================================';
END $$;

-- 显示所有API Keys（不显示密码）
SELECT 
    key_id,
    key_name,
    key_type,
    is_active,
    created_at,
    '请修改默认密码！' as warning
FROM api_keys
ORDER BY created_at;

-- 显示所有设备
SELECT 
    device_id,
    device_name,
    local_ip,
    hostname,
    status,
    last_heartbeat
FROM devices
ORDER BY device_name;
