-- M4文件管理模块 - 数据库表创建脚本
-- 创建时间: 2025-12-13
-- 模块: M4-01, M4-02, M4-03, M4-04

-- ==================== M4-01: 文件列表查询 ====================

-- 文件列表任务表
CREATE TABLE IF NOT EXISTS file_list_tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    path TEXT NOT NULL,
    recursive BOOLEAN DEFAULT FALSE,
    include_hidden BOOLEAN DEFAULT FALSE,
    file_types JSONB,
    sort_by VARCHAR(32) DEFAULT 'name',
    sort_order VARCHAR(8) DEFAULT 'asc',
    max_depth INTEGER DEFAULT 5,
    status VARCHAR(32) DEFAULT 'pending',
    total_files INTEGER DEFAULT 0,
    total_directories INTEGER DEFAULT 0,
    total_size BIGINT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 文件信息表
CREATE TABLE IF NOT EXISTS file_list_results (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL REFERENCES file_list_tasks(task_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    type VARCHAR(16) NOT NULL,
    size BIGINT DEFAULT 0,
    modified_time TIMESTAMP,
    permissions VARCHAR(16),
    owner VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_file_list_tasks_device 
ON file_list_tasks(device_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_file_list_tasks_status 
ON file_list_tasks(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_file_list_results_task 
ON file_list_results(task_id);

-- ==================== M4-02: 文件上传 ====================

-- 文件上传任务表
CREATE TABLE IF NOT EXISTS file_upload_tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    destination_path TEXT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    file_hash VARCHAR(64),
    overwrite BOOLEAN DEFAULT FALSE,
    create_dirs BOOLEAN DEFAULT TRUE,
    chunk_size INTEGER DEFAULT 1048576,
    status VARCHAR(32) DEFAULT 'pending',
    uploaded_size BIGINT DEFAULT 0,
    progress FLOAT DEFAULT 0.0,
    storage_path TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 文件分块表
CREATE TABLE IF NOT EXISTS file_upload_chunks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL REFERENCES file_upload_tasks(task_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_size INTEGER NOT NULL,
    chunk_hash VARCHAR(64),
    uploaded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, chunk_index)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_file_upload_tasks_device 
ON file_upload_tasks(device_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_file_upload_tasks_status 
ON file_upload_tasks(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_file_upload_chunks_task 
ON file_upload_chunks(task_id, chunk_index);

-- ==================== M4-03: 文件下载 ====================

-- 文件下载任务表
CREATE TABLE IF NOT EXISTS file_download_tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    source_path TEXT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_size BIGINT DEFAULT 0,
    file_hash VARCHAR(64),
    verify_hash BOOLEAN DEFAULT TRUE,
    status VARCHAR(32) DEFAULT 'pending',
    downloaded_size BIGINT DEFAULT 0,
    progress FLOAT DEFAULT 0.0,
    storage_path TEXT,
    download_url TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_file_download_tasks_device 
ON file_download_tasks(device_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_file_download_tasks_status 
ON file_download_tasks(status, created_at DESC);

-- ==================== M4-04: 文件操作 ====================

-- 文件操作任务表
CREATE TABLE IF NOT EXISTS file_operation_tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    operation VARCHAR(32) NOT NULL,
    source_path TEXT NOT NULL,
    destination_path TEXT,
    recursive BOOLEAN DEFAULT FALSE,
    force BOOLEAN DEFAULT FALSE,
    create_dirs BOOLEAN DEFAULT TRUE,
    status VARCHAR(32) DEFAULT 'pending',
    files_affected INTEGER DEFAULT 0,
    bytes_processed BIGINT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_file_operation_tasks_device 
ON file_operation_tasks(device_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_file_operation_tasks_status 
ON file_operation_tasks(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_file_operation_tasks_operation 
ON file_operation_tasks(operation, created_at DESC);

-- ==================== 表总结 ====================
-- M4-01: 2张表 (file_list_tasks, file_list_results)
-- M4-02: 2张表 (file_upload_tasks, file_upload_chunks)
-- M4-03: 1张表 (file_download_tasks)
-- M4-04: 1张表 (file_operation_tasks)
-- 总计: 6张表
