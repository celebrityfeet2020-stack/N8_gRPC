"""快速验证Session管理模块"""

from session_manager import SessionManager
from api_key_manager import APIKeyManager

# 数据库连接
DATABASE_URL = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"

# 创建管理器
session_mgr = SessionManager(DATABASE_URL)
api_key_mgr = APIKeyManager(DATABASE_URL)

print("=" * 60)
print("快速验证Session管理模块")
print("=" * 60)

# 准备：获取一个API Key ID
print("\n[准备] 获取测试API Key")
api_keys = api_key_mgr.list_api_keys(limit=1)
if not api_keys:
    print("❌ 没有找到API Key，请先创建")
    exit(1)
test_api_key_id = api_keys[0]['id']
print(f"✅ 使用API Key: {api_keys[0]['api_name']} (ID={test_api_key_id})")

# 测试1：生成Session Token
print("\n[测试1] 生成Session Token")
session_token = session_mgr.generate_session_token()
print(f"✅ 生成的Session Token: {session_token[:30]}... (长度: {len(session_token)})")

# 测试2：创建Session
print("\n[测试2] 创建Session")
session = session_mgr.create_session(
    api_key_id=test_api_key_id,
    device_id="test_device",
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0 Test",
    session_hours=72
)
print(f"✅ 创建成功: ID={session['id']}")
print(f"   Token: {session['session_token'][:30]}...")
print(f"   过期时间: {session['expires_at']}")
test_session_token = session['session_token']
test_session_id = session['id']

# 测试3：验证Session
print("\n[测试3] 验证Session")
verified = session_mgr.verify_session(test_session_token)
if verified:
    print(f"✅ 验证成功:")
    print(f"   API Name: {verified['api_name']}")
    print(f"   API Type: {verified['api_type']}")
    print(f"   Device ID: {verified['device_id']}")
else:
    print("❌ 验证失败")

# 测试4：刷新Session
print("\n[测试4] 刷新Session")
success = session_mgr.refresh_session(test_session_token, extend_hours=72)
print(f"✅ 刷新成功: {success}")

# 测试5：列出Sessions
print("\n[测试5] 列出Sessions")
sessions = session_mgr.list_sessions(limit=5)
print(f"✅ 找到 {len(sessions)} 个Sessions:")
for s in sessions:
    print(f"   - {s['api_name']} ({s['device_id']}) - 过期: {s['expires_at']}")

# 测试6：获取活跃Session数量
print("\n[测试6] 获取活跃Session数量")
count = session_mgr.get_active_session_count()
print(f"✅ 活跃Session数量: {count}")

# 测试7：根据ID获取Session
print("\n[测试7] 根据ID获取Session")
session_info = session_mgr.get_session_by_id(test_session_id)
if session_info:
    print(f"✅ 获取成功: {session_info['api_name']}")
else:
    print("❌ 获取失败")

# 测试8：删除Session
print("\n[测试8] 删除Session")
success = session_mgr.delete_session(test_session_token)
print(f"✅ 删除成功: {success}")

# 验证删除
verified = session_mgr.verify_session(test_session_token)
if verified is None:
    print("✅ 验证：Session已删除")
else:
    print("❌ 验证：Session仍然存在")

# 测试9：清理过期Sessions
print("\n[测试9] 清理过期Sessions")
cleaned = session_mgr.cleanup_expired_sessions()
print(f"✅ 清理了 {cleaned} 个过期Session")

print("\n" + "=" * 60)
print("快速验证完成！")
print("=" * 60)
