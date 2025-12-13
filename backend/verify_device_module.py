"""
N8枢纽控制中心 - 设备注册模块本地验证脚本
验证模块导入和基本结构（不需要数据库连接）
"""

import sys
import inspect


def verify_module():
    """验证设备注册模块"""
    
    print("=" * 60)
    print("N8 Hub Control Center - 设备注册模块验证")
    print("=" * 60)
    print()
    
    # ==================== 测试1：导入模块 ====================
    print("【测试1】导入模块")
    print("-" * 60)
    
    try:
        import device_registration
        print("✅ device_registration模块导入成功")
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False
    
    # ==================== 测试2：检查Pydantic模型 ====================
    print("\n【测试2】检查Pydantic模型")
    print("-" * 60)
    
    try:
        from device_registration import (
            DeviceRegisterRequest,
            DeviceUpdateRequest,
            DeviceResponse
        )
        
        models = [
            ('DeviceRegisterRequest', DeviceRegisterRequest),
            ('DeviceUpdateRequest', DeviceUpdateRequest),
            ('DeviceResponse', DeviceResponse)
        ]
        
        for name, model in models:
            print(f"   ✅ {name} 模型存在")
            
            # 检查字段
            fields = model.__fields__
            print(f"      字段数量: {len(fields)}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试3：检查DeviceRegistrationManager类 ====================
    print("\n【测试3】检查DeviceRegistrationManager类")
    print("-" * 60)
    
    try:
        from device_registration import DeviceRegistrationManager
        print("✅ DeviceRegistrationManager类存在")
        
        # 检查方法
        methods = [
            'generate_device_id',
            'register_device',
            'get_device',
            'list_devices',
            'update_device',
            'delete_device',
            'update_device_status',
            'get_device_count'
        ]
        
        for method in methods:
            if hasattr(DeviceRegistrationManager, method):
                print(f"   ✅ {method}() 方法存在")
            else:
                print(f"   ❌ {method}() 方法缺失")
                return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试4：检查API路由 ====================
    print("\n【测试4】检查API路由")
    print("-" * 60)
    
    try:
        from device_registration import router
        print(f"✅ router对象存在")
        print(f"   前缀: {router.prefix}")
        print(f"   标签: {router.tags}")
        
        # 统计路由数量
        route_count = len(router.routes)
        print(f"   路由数量: {route_count}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试5：检查全局函数 ====================
    print("\n【测试5】检查全局函数")
    print("-" * 60)
    
    try:
        from device_registration import (
            init_device_manager,
            get_device_manager
        )
        
        functions = [
            ('init_device_manager', init_device_manager),
            ('get_device_manager', get_device_manager)
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
    
    # ==================== 测试6：检查端点函数 ====================
    print("\n【测试6】检查端点函数")
    print("-" * 60)
    
    try:
        from device_registration import (
            register_device,
            list_devices,
            get_device,
            update_device,
            delete_device
        )
        
        endpoints = [
            'register_device',
            'list_devices',
            'get_device',
            'update_device',
            'delete_device'
        ]
        
        for endpoint_name in endpoints:
            print(f"   ✅ {endpoint_name}() 函数存在")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # ==================== 测试7：测试设备ID生成（无需数据库） ====================
    print("\n【测试7】测试设备ID生成（无需数据库）")
    print("-" * 60)
    
    try:
        from device_registration import DeviceRegistrationManager
        
        # 创建临时实例（不连接数据库）
        mgr = DeviceRegistrationManager("postgresql://dummy")
        
        # 测试ID生成
        id1 = mgr.generate_device_id("192.168.9.125", "ubuntu-server")
        id2 = mgr.generate_device_id("192.168.9.125", "ubuntu-server")
        id3 = mgr.generate_device_id("192.168.9.126", "ubuntu-server")
        
        print(f"   ✅ 设备ID生成成功")
        print(f"      相同参数ID1: {id1}")
        print(f"      相同参数ID2: {id2}")
        print(f"      不同参数ID3: {id3}")
        
        if id1 == id2:
            print(f"   ✅ 相同参数生成相同ID")
        else:
            print(f"   ❌ 相同参数应该生成相同ID")
            return False
        
        if id1 != id3:
            print(f"   ✅ 不同参数生成不同ID")
        else:
            print(f"   ❌ 不同参数应该生成不同ID")
            return False
        
        # 检查ID格式
        if id1.startswith("device-") and len(id1) == 23:  # device- + 16字符hash
            print(f"   ✅ ID格式正确 (device-{{16个字符}})")
        else:
            print(f"   ⚠️ ID格式可能不符合预期")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    # ==================== 测试8：检查方法签名 ====================
    print("\n【测试8】检查方法签名")
    print("-" * 60)
    
    try:
        from device_registration import DeviceRegistrationManager
        
        # 检查register_device签名
        sig = inspect.signature(DeviceRegistrationManager.register_device)
        params = list(sig.parameters.keys())
        print(f"   ✅ register_device() 参数: {params}")
        
        # 检查list_devices签名
        sig = inspect.signature(DeviceRegistrationManager.list_devices)
        params = list(sig.parameters.keys())
        print(f"   ✅ list_devices() 参数: {params}")
        
        # 检查update_device签名
        sig = inspect.signature(DeviceRegistrationManager.update_device)
        params = list(sig.parameters.keys())
        print(f"   ✅ update_device() 参数: {params}")
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
