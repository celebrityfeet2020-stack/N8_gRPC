"""
N8枢纽控制中心 - API Key管理模块单元测试
"""

import pytest
import os
from api_key_manager import APIKeyManager


# 测试数据库URL（使用环境变量或默认值）
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"
)


@pytest.fixture
def api_key_manager():
    """创建API Key管理器实例"""
    return APIKeyManager(TEST_DATABASE_URL)


@pytest.fixture
def test_api_key(api_key_manager):
    """创建测试用的API Key"""
    result = api_key_manager.create_api_key(
        api_name="Test API",
        api_type="internal",
        secret="test_secret_123",
        permissions=["read", "write"],
        created_by="pytest"
    )
    yield result
    # 清理：删除测试API Key
    api_key_manager.delete_api_key(result['id'])


class TestAPIKeyManager:
    """API Key管理器测试类"""
    
    def test_generate_api_key(self, api_key_manager):
        """测试生成API Key"""
        api_key = api_key_manager.generate_api_key()
        assert len(api_key) == 64
        assert isinstance(api_key, str)
    
    def test_hash_and_verify_secret(self, api_key_manager):
        """测试密钥哈希和验证"""
        secret = "my_secret_password"
        hashed = api_key_manager.hash_secret(secret)
        
        # 验证正确的密钥
        assert api_key_manager.verify_secret(secret, hashed) is True
        
        # 验证错误的密钥
        assert api_key_manager.verify_secret("wrong_password", hashed) is False
    
    def test_create_api_key(self, api_key_manager):
        """测试创建API Key"""
        result = api_key_manager.create_api_key(
            api_name="Test Create API",
            api_type="web",
            secret="create_test_secret",
            permissions=["*"],
            created_by="pytest"
        )
        
        try:
            assert result['api_name'] == "Test Create API"
            assert result['api_type'] == "web"
            assert result['is_active'] is True
            assert 'api_key' in result
            assert 'id' in result
        finally:
            # 清理
            api_key_manager.delete_api_key(result['id'])
    
    def test_create_api_key_invalid_type(self, api_key_manager):
        """测试创建API Key时使用无效类型"""
        with pytest.raises(ValueError):
            api_key_manager.create_api_key(
                api_name="Invalid Type API",
                api_type="invalid_type",
                secret="test_secret"
            )
    
    def test_verify_api_key_success(self, api_key_manager, test_api_key):
        """测试验证API Key成功"""
        result = api_key_manager.verify_api_key(
            test_api_key['api_key'],
            "test_secret_123"
        )
        
        assert result is not None
        assert result['api_name'] == "Test API"
        assert result['api_type'] == "internal"
        assert 'hashed_secret' not in result  # 不应该返回哈希值
    
    def test_verify_api_key_wrong_secret(self, api_key_manager, test_api_key):
        """测试验证API Key时密钥错误"""
        result = api_key_manager.verify_api_key(
            test_api_key['api_key'],
            "wrong_secret"
        )
        
        assert result is None
    
    def test_verify_api_key_not_exist(self, api_key_manager):
        """测试验证不存在的API Key"""
        result = api_key_manager.verify_api_key(
            "non_existent_key",
            "any_secret"
        )
        
        assert result is None
    
    def test_list_api_keys(self, api_key_manager, test_api_key):
        """测试列出API Keys"""
        results = api_key_manager.list_api_keys(limit=10)
        
        assert isinstance(results, list)
        assert len(results) > 0
        
        # 检查是否包含测试API Key
        test_key_found = any(r['id'] == test_api_key['id'] for r in results)
        assert test_key_found is True
    
    def test_list_api_keys_filter_by_type(self, api_key_manager, test_api_key):
        """测试按类型过滤API Keys"""
        results = api_key_manager.list_api_keys(api_type="internal")
        
        assert isinstance(results, list)
        assert all(r['api_type'] == "internal" for r in results)
    
    def test_get_api_key_by_id(self, api_key_manager, test_api_key):
        """测试根据ID获取API Key"""
        result = api_key_manager.get_api_key_by_id(test_api_key['id'])
        
        assert result is not None
        assert result['id'] == test_api_key['id']
        assert result['api_name'] == "Test API"
    
    def test_get_api_key_by_id_not_exist(self, api_key_manager):
        """测试获取不存在的API Key"""
        result = api_key_manager.get_api_key_by_id(999999)
        
        assert result is None
    
    def test_update_api_key(self, api_key_manager, test_api_key):
        """测试更新API Key"""
        success = api_key_manager.update_api_key(
            test_api_key['id'],
            api_name="Updated Test API",
            permissions=["read"]
        )
        
        assert success is True
        
        # 验证更新
        updated = api_key_manager.get_api_key_by_id(test_api_key['id'])
        assert updated['api_name'] == "Updated Test API"
    
    def test_deactivate_api_key(self, api_key_manager, test_api_key):
        """测试停用API Key"""
        success = api_key_manager.deactivate_api_key(test_api_key['id'])
        
        assert success is True
        
        # 验证停用后无法验证
        result = api_key_manager.verify_api_key(
            test_api_key['api_key'],
            "test_secret_123"
        )
        assert result is None
    
    def test_delete_api_key(self, api_key_manager):
        """测试删除API Key"""
        # 创建临时API Key
        temp_key = api_key_manager.create_api_key(
            api_name="Temp API",
            api_type="internal",
            secret="temp_secret"
        )
        
        # 删除
        success = api_key_manager.delete_api_key(temp_key['id'])
        assert success is True
        
        # 验证已删除
        result = api_key_manager.get_api_key_by_id(temp_key['id'])
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
