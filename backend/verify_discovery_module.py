"""
N8枢纽控制中心 - 功能发现API本地验证脚本
验证模块导入和基本结构（不需要数据库连接）
"""

import sys


def verify_module():
    """验证功能发现API模块"""
    
    print("=" * 60)
    print("N8 Hub Control Center - 功能发现API模块验证")
    print("=" * 60)
    print()
    
    # ==================== 测试1：导入模块 ====================
    print("【测试1】导入模块")
    print("-" * 60)
    
    try:
        import discovery_api
        print("✅ discovery_api模块导入成功")
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False
    
    # ==================== 测试2：检查常量 ====================
    print("\n【测试2】检查常量定义")
    print("-" * 60)
    
    try:
        from discovery_api import (
            API_VERSION,
            SYSTEM_CAPABILITIES,
            PERMISSION_DEFINITIONS,
            API_TYPE_DESCRIPTIONS
        )
        
        print(f"✅ API_VERSION: {API_VERSION['version']}")
        print(f"✅ SYSTEM_CAPABILITIES: {len(SYSTEM_CAPABILITIES)} 个功能")
        print(f"✅ PERMISSION_DEFINITIONS: {len(PERMISSION_DEFINITIONS)} 个权限")
        print(f"✅ API_TYPE_DESCRIPTIONS: {len(API_TYPE_DESCRIPTIONS)} 种API类型")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试3：检查路由 ====================
    print("\n【测试3】检查API路由")
    print("-" * 60)
    
    try:
        from discovery_api import router
        print(f"✅ router对象存在")
        print(f"   前缀: {router.prefix}")
        print(f"   标签: {router.tags}")
        
        # 统计路由数量
        route_count = len(router.routes)
        print(f"   路由数量: {route_count}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试4：检查功能清单 ====================
    print("\n【测试4】检查功能清单")
    print("-" * 60)
    
    try:
        from discovery_api import SYSTEM_CAPABILITIES
        
        # 列出所有功能
        print(f"   系统功能:")
        for cap_id, cap_info in SYSTEM_CAPABILITIES.items():
            endpoint_count = len(cap_info['endpoints'])
            perm_count = len(cap_info['required_permissions'])
            print(f"   - {cap_id}: {cap_info['name']}")
            print(f"     端点: {endpoint_count}, 权限: {perm_count}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试5：检查权限定义 ====================
    print("\n【测试5】检查权限定义")
    print("-" * 60)
    
    try:
        from discovery_api import PERMISSION_DEFINITIONS
        
        # 按类别统计权限
        categories = {}
        for perm_id, perm_info in PERMISSION_DEFINITIONS.items():
            category = perm_info['category']
            categories[category] = categories.get(category, 0) + 1
        
        print(f"   权限按类别统计:")
        for category, count in categories.items():
            print(f"   - {category}: {count}个")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试6：检查API类型 ====================
    print("\n【测试6】检查API类型定义")
    print("-" * 60)
    
    try:
        from discovery_api import API_TYPE_DESCRIPTIONS
        
        for api_type, info in API_TYPE_DESCRIPTIONS.items():
            print(f"   - {api_type}: {info['name']}")
            print(f"     认证方式: {info['authentication']}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试7：检查端点函数 ====================
    print("\n【测试7】检查端点函数")
    print("-" * 60)
    
    try:
        from discovery_api import (
            get_api_version,
            get_capabilities,
            get_permissions,
            get_api_types,
            get_endpoints,
            health_check
        )
        
        functions = [
            'get_api_version',
            'get_capabilities',
            'get_permissions',
            'get_api_types',
            'get_endpoints',
            'health_check'
        ]
        
        for func_name in functions:
            print(f"   ✅ {func_name}() 函数存在")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试8：验证数据一致性 ====================
    print("\n【测试8】验证数据一致性")
    print("-" * 60)
    
    try:
        from discovery_api import SYSTEM_CAPABILITIES, PERMISSION_DEFINITIONS
        
        # 检查功能中引用的权限是否都已定义
        all_required_perms = set()
        for cap_info in SYSTEM_CAPABILITIES.values():
            all_required_perms.update(cap_info['required_permissions'])
        
        defined_perms = set(PERMISSION_DEFINITIONS.keys())
        
        # 找出未定义的权限
        undefined_perms = all_required_perms - defined_perms
        if undefined_perms:
            print(f"   ⚠️ 发现未定义的权限: {undefined_perms}")
        else:
            print(f"   ✅ 所有权限都已定义")
        
        # 找出未使用的权限
        unused_perms = defined_perms - all_required_perms
        if unused_perms:
            print(f"   ℹ️ 未使用的权限: {unused_perms}")
        else:
            print(f"   ✅ 所有定义的权限都被使用")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 完成 ====================
    print("\n" + "=" * 60)
    print("✅ 所有验证通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = verify_module()
    sys.exit(0 if success else 1)
