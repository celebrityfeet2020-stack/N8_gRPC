"""快速验证API Key管理模块"""

from api_key_manager import APIKeyManager

# 数据库连接
DATABASE_URL = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"

# 创建管理器
manager = APIKeyManager(DATABASE_URL)

print("=" * 60)
print("快速验证API Key管理模块")
print("=" * 60)

# 测试1：生成API Key
print("\n[测试1] 生成API Key")
api_key = manager.generate_api_key()
print(f"✅ 生成的API Key: {api_key[:20]}... (长度: {len(api_key)})")

# 测试2：哈希和验证
print("\n[测试2] 密钥哈希和验证")
secret = "test_password_123"
hashed = manager.hash_secret(secret)
print(f"✅ 哈希值: {hashed[:30]}...")
is_valid = manager.verify_secret(secret, hashed)
print(f"✅ 验证正确密钥: {is_valid}")
is_invalid = manager.verify_secret("wrong_password", hashed)
print(f"✅ 验证错误密钥: {is_invalid}")

# 测试3：创建API Key
print("\n[测试3] 创建API Key")
try:
    result = manager.create_api_key(
        api_name="测试API",
        api_type="internal",
        secret="my_secret_key",
        permissions=["read", "write"],
        created_by="quick_test"
    )
    print(f"✅ 创建成功: ID={result['id']}, Name={result['api_name']}")
    test_api_id = result['id']
    test_api_key = result['api_key']
except Exception as e:
    print(f"❌ 创建失败: {e}")
    test_api_id = None
    test_api_key = None

# 测试4：验证API Key
if test_api_key:
    print("\n[测试4] 验证API Key")
    verified = manager.verify_api_key(test_api_key, "my_secret_key")
    if verified:
        print(f"✅ 验证成功: {verified['api_name']}")
    else:
        print("❌ 验证失败")

# 测试5：列出API Keys
print("\n[测试5] 列出API Keys")
api_keys = manager.list_api_keys(limit=5)
print(f"✅ 找到 {len(api_keys)} 个API Keys:")
for key in api_keys:
    print(f"  - {key['api_name']} ({key['api_type']})")

# 测试6：更新API Key
if test_api_id:
    print("\n[测试6] 更新API Key")
    success = manager.update_api_key(test_api_id, api_name="更新后的测试API")
    print(f"✅ 更新成功: {success}")

# 测试7：删除API Key
if test_api_id:
    print("\n[测试7] 删除API Key")
    success = manager.delete_api_key(test_api_id)
    print(f"✅ 删除成功: {success}")

print("\n" + "=" * 60)
print("快速验证完成！")
print("=" * 60)
