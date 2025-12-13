import axios from 'axios';

// 从环境变量获取API地址，默认为VPS1网关地址 (端口改为 14032)
// 在内网部署时，可以通过环境变量覆盖为 http://localhost:14032
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://43.160.207.239:14032';

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// 请求拦截器：添加API Key
api.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('n8_api_key');
  if (apiKey) {
    config.headers.Authorization = `Bearer ${apiKey}`;
  }
  return config;
});

// 响应拦截器：处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // API Key无效或过期
      localStorage.removeItem('n8_api_key');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export interface Device {
  id: number;
  device_id: string;
  hostname: string;
  os_type: string;
  os_version: string;
  agent_version: string;
  status: 'online' | 'offline';
  last_seen_at: string;
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  uptime: number;
  running_services: string[];
  metadata: Record<string, any>;
}

export interface Command {
  id: number;
  command_id: string;
  device_id: string;
  command_type: string;
  payload: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  success?: boolean;
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  executed_at?: string;
  duration_ms?: number;
  created_at: string;
  created_by?: string;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: 'ADMIN' | 'OPERATOR' | 'VIEWER' | 'AGENT';
  is_active: boolean;
  description?: string;
  created_at: string;
}

export interface ApiKey {
  id: number;
  name: string;
  is_active: boolean;
  expires_at?: string;
  last_used_at?: string;
  created_at: string;
  key_preview: string;
  key?: string; // 仅在创建时返回
}

export const deviceApi = {
  list: () => api.get<Device[]>('/api/devices').then(res => res.data),
  get: (id: string) => api.get<Device>(`/api/devices/${id}`).then(res => res.data),
  execute: (id: string, command: string, timeout: number = 30) => 
    api.post<Command>(`/api/devices/${id}/execute`, {
      command_type: 'exec',
      payload: { command },
      timeout
    }).then(res => res.data),
  restartService: (id: string, service: string) =>
    api.post<Command>(`/api/devices/${id}/execute`, {
      command_type: 'restart',
      payload: { service },
      timeout: 60
    }).then(res => res.data),
  getCommand: (cmdId: string) => api.get<Command>(`/api/commands/${cmdId}`).then(res => res.data),
  listCommands: (deviceId: string) => api.get<Command[]>(`/api/devices/${deviceId}/commands`).then(res => res.data),
};

export const userApi = {
  me: () => api.get<User>('/api/users/me').then(res => res.data),
  list: () => api.get<User[]>('/api/users').then(res => res.data),
  create: (data: Partial<User>) => api.post<User>('/api/users', data).then(res => res.data),
  listApiKeys: (userId: number) => api.get<ApiKey[]>(`/api/users/${userId}/api-keys`).then(res => res.data),
  createApiKey: (userId: number, name: string, days?: number) => 
    api.post<ApiKey>(`/api/users/${userId}/api-keys`, { name, expires_in_days: days }).then(res => res.data),
  revokeApiKey: (keyId: number) => api.delete(`/api/api-keys/${keyId}`).then(res => res.data),
};

export default api;
