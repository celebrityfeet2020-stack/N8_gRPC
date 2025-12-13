-- M3-01 Shell命令执行表
CREATE TABLE IF NOT EXISTS command_executions (
    command_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    command TEXT NOT NULL,
    working_dir VARCHAR(512),
    timeout INTEGER DEFAULT 300,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'timeout')),
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_command_executions_device_id ON command_executions(device_id);
CREATE INDEX IF NOT EXISTS idx_command_executions_status ON command_executions(status);
CREATE INDEX IF NOT EXISTS idx_command_executions_created_at ON command_executions(created_at DESC);

-- M3-02 屏幕截图表
CREATE TABLE IF NOT EXISTS screenshot_tasks (
    screenshot_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    monitor_index INTEGER,
    quality INTEGER DEFAULT 85 CHECK (quality >= 1 AND quality <= 100),
    format VARCHAR(10) DEFAULT 'png' CHECK (format IN ('png', 'jpg', 'bmp')),
    include_cursor BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    monitor_count INTEGER,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS screenshot_files (
    file_id SERIAL PRIMARY KEY,
    screenshot_id VARCHAR(32) NOT NULL REFERENCES screenshot_tasks(screenshot_id) ON DELETE CASCADE,
    monitor_index INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_screenshot_tasks_device_id ON screenshot_tasks(device_id);
CREATE INDEX IF NOT EXISTS idx_screenshot_tasks_status ON screenshot_tasks(status);
CREATE INDEX IF NOT EXISTS idx_screenshot_tasks_created_at ON screenshot_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_screenshot_files_screenshot_id ON screenshot_files(screenshot_id);

-- M3-03 鼠标键盘控制表
CREATE TABLE IF NOT EXISTS input_control_actions (
    action_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('mouse_move', 'mouse_click', 'keyboard_type', 'keyboard_press')),
    action_data JSONB NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_input_control_actions_device_id ON input_control_actions(device_id);
CREATE INDEX IF NOT EXISTS idx_input_control_actions_status ON input_control_actions(status);
CREATE INDEX IF NOT EXISTS idx_input_control_actions_created_at ON input_control_actions(created_at DESC);

-- M3-04 电源管理表
CREATE TABLE IF NOT EXISTS power_actions (
    action_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL CHECK (action IN ('shutdown', 'reboot', 'sleep', 'hibernate', 'logout')),
    force BOOLEAN DEFAULT FALSE,
    delay INTEGER DEFAULT 0,
    message TEXT,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'completed', 'failed', 'cancelled')),
    error_message TEXT,
    scheduled_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_power_actions_device_id ON power_actions(device_id);
CREATE INDEX IF NOT EXISTS idx_power_actions_status ON power_actions(status);
CREATE INDEX IF NOT EXISTS idx_power_actions_scheduled_at ON power_actions(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_power_actions_created_at ON power_actions(created_at DESC);

-- M3-05 服务管理表
CREATE TABLE IF NOT EXISTS service_actions (
    action_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    service_name VARCHAR(255) NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('start', 'stop', 'restart', 'status', 'enable', 'disable')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    result_data JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_service_actions_device_id ON service_actions(device_id);
CREATE INDEX IF NOT EXISTS idx_service_actions_status ON service_actions(status);
CREATE INDEX IF NOT EXISTS idx_service_actions_created_at ON service_actions(created_at DESC);

-- M3-06 注册表编辑表
CREATE TABLE IF NOT EXISTS registry_actions (
    action_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL CHECK (action IN ('read', 'write', 'delete', 'create_key', 'delete_key')),
    key_path TEXT NOT NULL,
    value_name VARCHAR(255),
    value_data TEXT,
    value_type VARCHAR(50) DEFAULT 'REG_SZ',
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    result_data JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_registry_actions_device_id ON registry_actions(device_id);
CREATE INDEX IF NOT EXISTS idx_registry_actions_status ON registry_actions(status);
CREATE INDEX IF NOT EXISTS idx_registry_actions_created_at ON registry_actions(created_at DESC);

-- M3-07 环境变量管理表
CREATE TABLE IF NOT EXISTS environment_actions (
    action_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL CHECK (action IN ('get', 'set', 'delete', 'list')),
    var_name VARCHAR(255),
    var_value TEXT,
    scope VARCHAR(20) DEFAULT 'user' CHECK (scope IN ('user', 'system', 'session', 'permanent')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    result_data JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_environment_actions_device_id ON environment_actions(device_id);
CREATE INDEX IF NOT EXISTS idx_environment_actions_status ON environment_actions(status);
CREATE INDEX IF NOT EXISTS idx_environment_actions_created_at ON environment_actions(created_at DESC);

-- M3-08 性能基准测试表
CREATE TABLE IF NOT EXISTS benchmark_tasks (
    benchmark_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    test_types TEXT[] NOT NULL,
    duration INTEGER DEFAULT 30,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    result_data JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_benchmark_tasks_device_id ON benchmark_tasks(device_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_tasks_status ON benchmark_tasks(status);
CREATE INDEX IF NOT EXISTS idx_benchmark_tasks_created_at ON benchmark_tasks(created_at DESC);
