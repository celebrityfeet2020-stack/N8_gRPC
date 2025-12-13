-- M5进程管理 + M6系统监控模块 - 数据库表创建脚本
-- 创建时间: 2024-12-13
-- 模块: M5 (4个子模块), M6 (7个子模块)

-- ==================== M5: 进程管理 ====================

-- 进程列表任务表
CREATE TABLE IF NOT EXISTS process_list_tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    name_filter TEXT,
    sort_by VARCHAR(32) DEFAULT 'cpu',
    sort_order VARCHAR(8) DEFAULT 'desc',
    limit_count INTEGER DEFAULT 100,
    status VARCHAR(32) DEFAULT 'pending',
    process_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 进程信息表
CREATE TABLE IF NOT EXISTS process_list_results (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL REFERENCES process_list_tasks(task_id) ON DELETE CASCADE,
    pid INTEGER NOT NULL,
    name TEXT NOT NULL,
    cpu_percent FLOAT DEFAULT 0.0,
    memory_percent FLOAT DEFAULT 0.0,
    memory_mb FLOAT DEFAULT 0.0,
    status TEXT,
    username TEXT,
    create_time TIMESTAMP,
    cmdline TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 进程操作任务表
CREATE TABLE IF NOT EXISTS process_action_tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    action VARCHAR(32) NOT NULL,
    pid INTEGER,
    command TEXT,
    working_dir TEXT,
    env_vars JSONB,
    force BOOLEAN DEFAULT FALSE,
    status VARCHAR(32) DEFAULT 'pending',
    result_pid INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- M5索引
CREATE INDEX IF NOT EXISTS idx_process_list_tasks_device 
ON process_list_tasks(device_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_process_list_results_task 
ON process_list_results(task_id);

CREATE INDEX IF NOT EXISTS idx_process_action_tasks_device 
ON process_action_tasks(device_id, created_at DESC);

-- ==================== M6: 系统监控 ====================

-- M6-01: 系统信息表
CREATE TABLE IF NOT EXISTS system_info (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    hostname TEXT,
    os_name TEXT,
    os_version TEXT,
    cpu_model TEXT,
    cpu_cores INTEGER,
    cpu_percent FLOAT,
    memory_total_mb FLOAT,
    memory_used_mb FLOAT,
    memory_percent FLOAT,
    disk_total_gb FLOAT,
    disk_used_gb FLOAT,
    disk_percent FLOAT,
    boot_time TIMESTAMP,
    uptime_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M6-02: 网络接口表
CREATE TABLE IF NOT EXISTS network_interfaces (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    name TEXT NOT NULL,
    ip_address TEXT,
    mac_address TEXT,
    netmask TEXT,
    status TEXT,
    speed_mbps INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M6-03: 网络流量表
CREATE TABLE IF NOT EXISTS network_traffic (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    interface TEXT NOT NULL,
    bytes_sent BIGINT,
    bytes_recv BIGINT,
    packets_sent BIGINT,
    packets_recv BIGINT,
    errors_in INTEGER,
    errors_out INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M6-04: 进程守护表
CREATE TABLE IF NOT EXISTS process_guards (
    guard_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    process_name TEXT NOT NULL,
    command TEXT NOT NULL,
    working_dir TEXT,
    check_interval INTEGER DEFAULT 60,
    restart_on_failure BOOLEAN DEFAULT TRUE,
    max_restarts INTEGER DEFAULT 3,
    restart_count INTEGER DEFAULT 0,
    status VARCHAR(32) DEFAULT 'active',
    last_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M6-05: Windows事件日志表
CREATE TABLE IF NOT EXISTS windows_event_logs (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    event_id INTEGER,
    level TEXT,
    source TEXT,
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M6-06: 性能历史表
CREATE TABLE IF NOT EXISTS performance_history (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    cpu_percent FLOAT,
    memory_percent FLOAT,
    disk_percent FLOAT,
    network_bytes_sent BIGINT,
    network_bytes_recv BIGINT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M6-07: 网络连接表
CREATE TABLE IF NOT EXISTS network_connections (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    local_address TEXT,
    local_port INTEGER,
    remote_address TEXT,
    remote_port INTEGER,
    status TEXT,
    pid INTEGER,
    process_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M6索引
CREATE INDEX IF NOT EXISTS idx_system_info_device 
ON system_info(device_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_network_interfaces_device 
ON network_interfaces(device_id);

CREATE INDEX IF NOT EXISTS idx_network_traffic_device 
ON network_traffic(device_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_process_guards_device 
ON process_guards(device_id, status);

CREATE INDEX IF NOT EXISTS idx_windows_event_logs_device 
ON windows_event_logs(device_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_performance_history_device 
ON performance_history(device_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_network_connections_device 
ON network_connections(device_id, created_at DESC);

-- ==================== 表总结 ====================
-- M5: 3张表 (process_list_tasks, process_list_results, process_action_tasks)
-- M6: 7张表 (system_info, network_interfaces, network_traffic, process_guards, 
--            windows_event_logs, performance_history, network_connections)
-- 总计: 10张表
