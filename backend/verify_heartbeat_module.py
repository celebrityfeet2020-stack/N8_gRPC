"""
N8枢纽控制中心 - 心跳检测模块本地验证脚本
验证模块导入和基本结构（不需要数据库连接）
"""

import sys


def verify_module():
    """验证心跳检测模块"""
    
    print("=" * 60)
    print("N8 Hub Control Center - 心跳检测模块验证")
    print("=" * 60)
    print()
    
    # ==================== 测试1：导入模块 ====================
    print("【测试1】导入模块")
    print("-" * 60)
    
    try:
        import heartbeat
        print("✅ heartbeat模块导入成功")
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False
    
    # ==================== 测试2：检查配置常量 ====================
    print("\n【测试2】检查配置常量")
    print("-" * 60)
    
    try:
        from heartbeat import HEARTBEAT_TIMEOUT, OFFLINE_CHECK_INTERVAL
        
        print(f"✅ HEARTBEAT_TIMEOUT: {HEARTBEAT_TIMEOUT}秒")
        print(f"✅ OFFLINE_CHECK_INTERVAL: {OFFLINE_CHECK_INTERVAL}秒")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试3：检查Pydantic模型 ====================
    print("\n【测试3】检查Pydantic模型")
    print("-" * 60)
    
    try:
        from heartbeat import HeartbeatRequest, HeartbeatResponse
        
        models = [
            ('HeartbeatRequest', HeartbeatRequest),
            ('HeartbeatResponse', HeartbeatResponse)
        ]
        
        for name, model in models:
            print(f"   ✅ {name} 模型存在")
            
            # 检查字段
            fields = model.model_fields
            print(f"      字段数量: {len(fields)}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试4：检查HeartbeatManager类 ====================
    print("\n【测试4】检查HeartbeatManager类")
    print("-" * 60)
    
    try:
        from heartbeat import HeartbeatManager
        print("✅ HeartbeatManager类存在")
        
        # 检查方法
        methods = [
            'report_heartbeat',
            'check_offline_devices',
            'get_device_heartbeat_status',
            'get_heartbeat_statistics'
        ]
        
        for method in methods:
            if hasattr(HeartbeatManager, method):
                print(f"   ✅ {method}() 方法存在")
            else:
                print(f"   ❌ {method}() 方法缺失")
                return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试5：检查API路由 ====================
    print("\n【测试5】检查API路由")
    print("-" * 60)
    
    try:
        from heartbeat import router
        print(f"✅ router对象存在")
        print(f"   前缀: {router.prefix}")
        print(f"   标签: {router.tags}")
        
        # 统计路由数量
        route_count = len(router.routes)
        print(f"   路由数量: {route_count}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试6：检查全局函数 ====================
    print("\n【测试6】检查全局函数")
    print("-" * 60)
    
    try:
        from heartbeat import init_heartbeat_manager, get_heartbeat_manager
        
        functions = [
            ('init_heartbeat_manager', init_heartbeat_manager),
            ('get_heartbeat_manager', get_heartbeat_manager)
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
    
    # ==================== 测试7：检查端点函数 ====================
    print("\n【测试7】检查端点函数")
    print("-" * 60)
    
    try:
        from heartbeat import (
            report_heartbeat,
            get_heartbeat_status,
            get_heartbeat_statistics,
            trigger_offline_check
        )
        
        endpoints = [
            'report_heartbeat',
            'get_heartbeat_status',
            'get_heartbeat_statistics',
            'trigger_offline_check'
        ]
        
        for endpoint_name in endpoints:
            print(f"   ✅ {endpoint_name}() 函数存在")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试8：验证HeartbeatManager初始化 ====================
    print("\n【测试8】验证HeartbeatManager初始化")
    print("-" * 60)
    
    try:
        from heartbeat import HeartbeatManager
        
        # 创建临时实例（不连接数据库）
        mgr = HeartbeatManager("postgresql://dummy")
        
        print(f"   ✅ HeartbeatManager实例创建成功")
        print(f"      heartbeat_timeout: {mgr.heartbeat_timeout}秒")
        print(f"      database_url: {mgr.database_url[:20]}...")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    # ==================== 测试9：检查Pydantic模型验证 ====================
    print("\n【测试9】检查Pydantic模型验证")
    print("-" * 60)
    
    try:
        from heartbeat import HeartbeatRequest
        
        # 测试有效数据
        valid_request = HeartbeatRequest(
            metrics={"cpu_usage": 50.0},
            metadata={"uptime": 86400}
        )
        print(f"   ✅ 有效数据验证通过")
        
        # 测试空数据（metrics和metadata都是可选的）
        empty_request = HeartbeatRequest()
        print(f"   ✅ 空数据验证通过（字段可选）")
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False
    
    # ==================== 测试10：检查路由路径 ====================
    print("\n【测试10】检查路由路径")
    print("-" * 60)
    
    try:
        from heartbeat import router
        
        # 提取路由路径
        paths = []
        for route in router.routes:
            if hasattr(route, 'path'):
                paths.append(f"{route.methods} {route.path}")
        
        print(f"   ✅ API端点:")
        for path in paths:
            print(f"      {path}")
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
