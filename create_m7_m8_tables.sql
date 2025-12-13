-- M7日志系统数据库表

-- M7-01: 命令执行日志表
CREATE TABLE IF NOT EXISTS command_logs_m7 (
    log_id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    command TEXT NOT NULL,
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_command_logs_device ON command_logs_m7(device_id);
CREATE INDEX IF NOT EXISTS idx_command_logs_created ON command_logs_m7(created_at DESC);

-- M7-02: Agent日志表
CREATE TABLE IF NOT EXISTS agent_logs (
    log_id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    level VARCHAR(20) NOT NULL,  -- debug, info, warning, error, critical
    message TEXT NOT NULL,
    module VARCHAR(255),
    function VARCHAR(255),
    line_number INTEGER,
    extra_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_device ON agent_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_level ON agent_logs(level);
CREATE INDEX IF NOT EXISTS idx_agent_logs_created ON agent_logs(created_at DESC);

-- M7-03: 系统事件日志表
CREATE TABLE IF NOT EXISTS system_event_logs (
    log_id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,  -- device_online, device_offline, task_created, etc.
    event_data JSONB,
    severity VARCHAR(20) DEFAULT 'info',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_event_logs_device ON system_event_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_system_event_logs_type ON system_event_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_system_event_logs_created ON system_event_logs(created_at DESC);


-- M8工作流编排数据库表

-- M8-01: 工作流表
CREATE TABLE IF NOT EXISTS workflows (
    workflow_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    workflow_type VARCHAR(50) NOT NULL,  -- device_backup, batch_command, health_check, custom
    config JSONB NOT NULL,
    schedule VARCHAR(100),  -- Cron表达式
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    last_execution_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflows_type ON workflows(workflow_type);
CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
CREATE INDEX IF NOT EXISTS idx_workflows_created ON workflows(created_at DESC);

-- M8-02/03/04: 工作流步骤表
CREATE TABLE IF NOT EXISTS workflow_steps (
    step_id VARCHAR(255) PRIMARY KEY,
    workflow_id VARCHAR(255) NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    step_name VARCHAR(255) NOT NULL,
    step_order INTEGER NOT NULL,
    action VARCHAR(100) NOT NULL,
    parameters JSONB,
    depends_on JSONB,  -- 依赖的步骤ID列表
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed, skipped
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_workflow ON workflow_steps(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_order ON workflow_steps(workflow_id, step_order);

-- M8-01: 工作流执行记录表
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id VARCHAR(255) PRIMARY KEY,
    workflow_id VARCHAR(255) NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed, cancelled
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_started ON workflow_executions(started_at DESC);
