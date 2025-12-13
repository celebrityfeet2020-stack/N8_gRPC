"""
N8枢纽控制中心 - 功能发现API测试脚本
测试功能发现API的各个端点
"""

import asyncio
from fastapi.testclient import TestClient
from discovery_example import app
from auth_middleware import init_auth_middleware
from api_key_manager import APIKeyManager
from session_manager import SessionManager


# 数据库连接URL
DATABASE_URL = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"


def test_discovery_api():
    """测试功能发现API"""
    
    print("=" * 60)
    print("N8 Hub Control Center - 功能发现API测试")
    print("=" * 60)
    print()
    
    # 初始化认证中间件
    init_auth_middleware(DATABASE_URL)
    
    # 创建测试客户端
    client = TestClient(app)
    
    # ==================== 测试1：获取API版本（无需认证） ====================
    print("【测试1】获取API版本（无需认证）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/version")
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ API版本: {data['data']['version']}")
        print(f"   发布日期: {data['data']['release_date']}")
        print(f"   支持的认证方式: {', '.join(data['data']['supported_auth_methods'])}")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
        return
    
    # ==================== 测试2：获取API类型说明（无需认证） ====================
    print("【测试2】获取API类型说明（无需认证）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/api-types")
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        api_types = data['data']['api_types']
        print(f"✅ 找到 {len(api_types)} 种API类型:")
        for api_type, info in api_types.items():
            print(f"   - {api_type}: {info['name']}")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 测试3：健康检查（无需认证） ====================
    print("【测试3】健康检查（无需认证）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/health")
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 服务状态: {data['status']}")
        print(f"   版本: {data['version']}")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 准备认证信息 ====================
    print("【准备】创建测试API Key和Session")
    print("-" * 60)
    
    try:
        # 创建API Key
        api_key_mgr = APIKeyManager(DATABASE_URL)
        api_key = api_key_mgr.generate_api_key()
        secret = api_key_mgr.generate_api_key()
        
        result = api_key_mgr.create_api_key(
            api_name="Test Discovery API",
            api_type="web",
            secret=secret,
            permissions=["device:read", "device:write", "device:control"],
            created_by="test_script"
        )
        
        api_key_id = result['id']
        print(f"✅ API Key创建成功 (ID: {api_key_id})")
        
        # 创建Session
        session_mgr = SessionManager(DATABASE_URL)
        session_result = session_mgr.create_session(
            api_key_id=api_key_id,
            device_id="test-device",
            ip_address="127.0.0.1"
        )
        
        session_token = session_result['session_token']
        print(f"✅ Session创建成功")
        print()
    except Exception as e:
        print(f"❌ 准备失败: {e}")
        return
    
    # ==================== 测试4：获取系统功能列表（需要认证） ====================
    print("【测试4】获取系统功能列表（需要认证）")
    print("-" * 60)
    
    headers = {"Authorization": f"Bearer {session_token}"}
    response = client.get("/api/v1/discovery/capabilities", headers=headers)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        capabilities = data['data']['capabilities']
        print(f"✅ 找到 {data['data']['total_count']} 个功能:")
        for cap_id, cap_info in list(capabilities.items())[:3]:
            print(f"   - {cap_id}: {cap_info['name']}")
            print(f"     端点数量: {len(cap_info['endpoints'])}")
        print(f"   ... (共{len(capabilities)}个)")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 测试5：按API类型过滤功能 ====================
    print("【测试5】按API类型过滤功能（api_type=web）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/capabilities?api_type=web", headers=headers)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Web API可用功能数: {data['data']['total_count']}")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 测试6：获取权限列表 ====================
    print("【测试6】获取权限列表（需要认证）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/permissions", headers=headers)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        permissions = data['data']['permissions']
        user_permissions = data['data']['user_permissions']
        
        print(f"✅ 系统权限总数: {data['data']['total_count']}")
        print(f"   用户拥有权限: {len(user_permissions)}")
        print(f"   权限列表: {', '.join(user_permissions)}")
        
        # 统计已授权和未授权的权限
        granted_count = sum(1 for p in permissions.values() if p['granted'])
        print(f"   已授权: {granted_count}, 未授权: {len(permissions) - granted_count}")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 测试7：按类别过滤权限 ====================
    print("【测试7】按类别过滤权限（category=device_management）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/permissions?category=device_management", headers=headers)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 设备管理相关权限数: {data['data']['total_count']}")
        for perm_id, perm_info in data['data']['permissions'].items():
            status = "✓" if perm_info['granted'] else "✗"
            print(f"   [{status}] {perm_id}: {perm_info['name']}")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 测试8：获取API端点列表 ====================
    print("【测试8】获取API端点列表（需要认证）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/endpoints", headers=headers)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        endpoints = data['data']['endpoints']
        print(f"✅ 找到 {data['data']['total_count']} 个端点")
        
        # 按HTTP方法统计
        methods = {}
        for endpoint in endpoints:
            method = endpoint['method']
            methods[method] = methods.get(method, 0) + 1
        
        print(f"   按方法统计:")
        for method, count in methods.items():
            print(f"   - {method}: {count}个")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 测试9：按功能过滤端点 ====================
    print("【测试9】按功能过滤端点（capability=device_management）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/endpoints?capability=device_management", headers=headers)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        endpoints = data['data']['endpoints']
        print(f"✅ 设备管理端点数: {data['data']['total_count']}")
        for endpoint in endpoints:
            print(f"   {endpoint['method']} {endpoint['path']}")
            print(f"      {endpoint['description']}")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 测试10：按HTTP方法过滤端点 ====================
    print("【测试10】按HTTP方法过滤端点（method=POST）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/endpoints?method=POST", headers=headers)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ POST端点数: {data['data']['total_count']}")
        print()
    else:
        print(f"❌ 请求失败: {response.text}")
    
    # ==================== 测试11：未认证访问（应该失败） ====================
    print("【测试11】未认证访问（应该失败）")
    print("-" * 60)
    
    response = client.get("/api/v1/discovery/capabilities")
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 401:
        print(f"✅ 正确拒绝了未认证请求")
        print()
    else:
        print(f"❌ 应该返回401，实际返回: {response.status_code}")
    
    # ==================== 清理：删除测试数据 ====================
    print("【清理】删除测试数据")
    print("-" * 60)
    
    try:
        session_mgr.delete_session(session_token)
        print(f"✅ Session已删除")
        
        api_key_mgr.delete_api_key(api_key_id)
        print(f"✅ API Key已删除")
        print()
    except Exception as e:
        print(f"⚠️ 清理失败: {e}")
    
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_discovery_api()
