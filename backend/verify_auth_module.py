"""
N8枢纽控制中心 - 认证中间件本地验证脚本
验证模块导入和基本结构（不需要数据库连接）
"""

import sys
import inspect


def verify_module():
    """验证认证中间件模块"""
    
    print("=" * 60)
    print("N8 Hub Control Center - 认证中间件模块验证")
    print("=" * 60)
    print()
    
    # ==================== 测试1：导入模块 ====================
    print("【测试1】导入模块")
    print("-" * 60)
    
    try:
        import auth_middleware
        print("✅ auth_middleware模块导入成功")
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False
    
    # ==================== 测试2：检查类 ====================
    print("\n【测试2】检查AuthMiddleware类")
    print("-" * 60)
    
    try:
        from auth_middleware import AuthMiddleware
        print("✅ AuthMiddleware类存在")
        
        # 检查方法
        methods = [
            'verify_session_token',
            'verify_api_key',
            'verify_session_or_api_key',
            'check_permissions',
            'require_permissions',
            'require_api_type'
        ]
        
        for method in methods:
            if hasattr(AuthMiddleware, method):
                print(f"   ✅ {method}() 方法存在")
            else:
                print(f"   ❌ {method}() 方法缺失")
                return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试3：检查全局函数 ====================
    print("\n【测试3】检查全局函数")
    print("-" * 60)
    
    try:
        from auth_middleware import (
            init_auth_middleware,
            get_auth_middleware,
            require_session,
            require_api_key,
            require_auth
        )
        
        functions = [
            ('init_auth_middleware', init_auth_middleware),
            ('get_auth_middleware', get_auth_middleware),
            ('require_session', require_session),
            ('require_api_key', require_api_key),
            ('require_auth', require_auth)
        ]
        
        for name, func in functions:
            if callable(func):
                print(f"   ✅ {name}() 函数存在")
            else:
                print(f"   ❌ {name}() 不是函数")
                return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试4：检查方法签名 ====================
    print("\n【测试4】检查方法签名")
    print("-" * 60)
    
    try:
        # 检查verify_session_token签名
        sig = inspect.signature(AuthMiddleware.verify_session_token)
        params = list(sig.parameters.keys())
        print(f"   ✅ verify_session_token() 参数: {params}")
        
        # 检查verify_api_key签名
        sig = inspect.signature(AuthMiddleware.verify_api_key)
        params = list(sig.parameters.keys())
        print(f"   ✅ verify_api_key() 参数: {params}")
        
        # 检查check_permissions签名
        sig = inspect.signature(AuthMiddleware.check_permissions)
        params = list(sig.parameters.keys())
        print(f"   ✅ check_permissions() 参数: {params}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试5：检查依赖项 ====================
    print("\n【测试5】检查依赖项")
    print("-" * 60)
    
    dependencies = [
        ('fastapi', 'FastAPI'),
        ('api_key_manager', 'APIKeyManager'),
        ('session_manager', 'SessionManager')
    ]
    
    for module_name, class_name in dependencies:
        try:
            module = __import__(module_name)
            if hasattr(module, class_name):
                print(f"   ✅ {module_name}.{class_name} 可用")
            else:
                print(f"   ⚠️ {module_name}.{class_name} 不存在")
        except ImportError:
            print(f"   ❌ {module_name} 模块无法导入")
            return False
    
    # ==================== 测试6：检查类型注解 ====================
    print("\n【测试6】检查类型注解")
    print("-" * 60)
    
    try:
        from auth_middleware import AuthMiddleware
        
        # 检查verify_session_token返回类型
        sig = inspect.signature(AuthMiddleware.verify_session_token)
        return_annotation = sig.return_annotation
        print(f"   ✅ verify_session_token() 返回类型: {return_annotation}")
        
        # 检查check_permissions返回类型
        sig = inspect.signature(AuthMiddleware.check_permissions)
        return_annotation = sig.return_annotation
        print(f"   ✅ check_permissions() 返回类型: {return_annotation}")
    except Exception as e:
        print(f"⚠️ 类型注解检查失败: {e}")
    
    # ==================== 完成 ====================
    print("\n" + "=" * 60)
    print("✅ 所有验证通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = verify_module()
    sys.exit(0 if success else 1)
