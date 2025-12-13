"""
N8枢纽控制中心 - 认证中间件测试脚本
快速验证认证中间件功能
"""

import asyncio
from datetime import datetime, timedelta
from fastapi.security import HTTPAuthorizationCredentials

from auth_middleware import AuthMiddleware
from api_key_manager import APIKeyManager
from session_manager import SessionManager


# 数据库连接URL
DATABASE_URL = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"


async def test_auth_middleware():
    """测试认证中间件"""
    
    print("=" * 60)
    print("N8 Hub Control Center - 认证中间件测试")
    print("=" * 60)
    print()
    
    # 初始化管理器
    auth = AuthMiddleware(DATABASE_URL)
    api_key_mgr = APIKeyManager(DATABASE_URL)
    session_mgr = SessionManager(DATABASE_URL)
    
    # ==================== 测试1：创建测试API Key ====================
    print("【测试1】创建测试API Key")
    print("-" * 60)
    
    try:
        # 生成API Key和Secret
        api_key = api_key_mgr.generate_api_key()
        secret = api_key_mgr.generate_api_key()  # 使用相同方法生成Secret
        
        # 创建API Key
        result = api_key_mgr.create_api_key(
            api_name="Test Web API",
            api_type="web",
            secret=secret,
            permissions=["device:read", "device:control"],
            created_by="test_script"
        )
        
        api_key_id = result['id']
        print(f"✅ API Key创建成功")
        print(f"   ID: {api_key_id}")
        print(f"   API Key: {api_key}")
        print(f"   Secret: {secret}")
        print(f"   权限: {result['permissions']}")
        print()
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return
    
    # ==================== 测试2：创建Session ====================
    print("【测试2】创建Session")
    print("-" * 60)
    
    try:
        session_result = session_mgr.create_session(
            api_key_id=api_key_id,
            device_id="test-device-001",
            ip_address="127.0.0.1",
            user_agent="Test Script"
        )
        
        session_token = session_result['session_token']
        print(f"✅ Session创建成功")
        print(f"   Session Token: {session_token[:32]}...")
        print(f"   过期时间: {session_result['expires_at']}")
        print()
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return
    
    # ==================== 测试3：验证Session Token ====================
    print("【测试3】验证Session Token")
    print("-" * 60)
    
    try:
        # 模拟HTTP Authorization头
        auth_creds = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=session_token
        )
        
        session_info = await auth.verify_session_token(auth_creds)
        print(f"✅ Session验证成功")
        print(f"   Session ID: {session_info['id']}")
        print(f"   API Key名称: {session_info['api_key']['api_name']}")
        print(f"   API类型: {session_info['api_key']['api_type']}")
        print()
    except Exception as e:
        print(f"❌ 验证失败: {e}")
    
    # ==================== 测试4：验证API Key ====================
    print("【测试4】验证API Key")
    print("-" * 60)
    
    try:
        api_key_info = await auth.verify_api_key(api_key, secret)
        print(f"✅ API Key验证成功")
        print(f"   API Key ID: {api_key_info['id']}")
        print(f"   API Key名称: {api_key_info['api_name']}")
        print(f"   API类型: {api_key_info['api_type']}")
        print(f"   权限: {api_key_info['permissions']}")
        print()
    except Exception as e:
        print(f"❌ 验证失败: {e}")
    
    # ==================== 测试5：验证错误的Secret ====================
    print("【测试5】验证错误的Secret")
    print("-" * 60)
    
    try:
        await auth.verify_api_key(api_key, "wrong_secret")
        print(f"❌ 应该验证失败但成功了")
    except Exception as e:
        print(f"✅ 正确拒绝了错误的Secret")
        print(f"   错误信息: {e.detail}")
        print()
    
    # ==================== 测试6：检查权限 ====================
    print("【测试6】检查权限")
    print("-" * 60)
    
    # 检查存在的权限
    has_permission = auth.check_permissions(session_info, ["device:read"])
    print(f"✅ 检查权限 device:read: {has_permission}")
    
    # 检查不存在的权限
    has_permission = auth.check_permissions(session_info, ["admin:write"])
    print(f"✅ 检查权限 admin:write: {has_permission}")
    
    # 检查多个权限
    has_permission = auth.check_permissions(session_info, ["device:read", "device:control"])
    print(f"✅ 检查权限 device:read + device:control: {has_permission}")
    print()
    
    # ==================== 测试7：验证Session或API Key ====================
    print("【测试7】验证Session或API Key（使用Session）")
    print("-" * 60)
    
    try:
        auth_creds = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=session_token
        )
        auth_info = await auth.verify_session_or_api_key(auth_creds, None, None)
        print(f"✅ 认证成功（使用Session Token）")
        print(f"   认证类型: Session")
        print()
    except Exception as e:
        print(f"❌ 认证失败: {e}")
    
    print("【测试8】验证Session或API Key（使用API Key）")
    print("-" * 60)
    
    try:
        auth_info = await auth.verify_session_or_api_key(None, api_key, secret)
        print(f"✅ 认证成功（使用API Key）")
        print(f"   认证类型: API Key")
        print()
    except Exception as e:
        print(f"❌ 认证失败: {e}")
    
    # ==================== 清理：删除测试数据 ====================
    print("【清理】删除测试数据")
    print("-" * 60)
    
    try:
        # 删除Session
        session_mgr.delete_session(session_token)
        print(f"✅ Session已删除")
        
        # 删除API Key
        api_key_mgr.delete_api_key(api_key_id)
        print(f"✅ API Key已删除")
        print()
    except Exception as e:
        print(f"⚠️ 清理失败: {e}")
    
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_auth_middleware())
