"""
N8枢纽控制中心 - 设备注册测试脚本
测试设备注册的各个功能
"""

from device_registration import DeviceRegistrationManager
from api_key_manager import APIKeyManager
from session_manager import SessionManager


# 数据库连接URL
DATABASE_URL = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"


def test_device_registration():
    """测试设备注册"""
    
    print("=" * 60)
    print("N8 Hub Control Center - 设备注册测试")
    print("=" * 60)
    print()
    
    # 初始化管理器
    device_mgr = DeviceRegistrationManager(DATABASE_URL)
    
    # ==================== 测试1：生成设备ID ====================
    print("【测试1】生成设备ID")
    print("-" * 60)
    
    try:
        device_id_1 = device_mgr.generate_device_id("192.168.9.125", "ubuntu-server")
        device_id_2 = device_mgr.generate_device_id("192.168.9.125", "ubuntu-server")
        device_id_3 = device_mgr.generate_device_id("192.168.9.126", "ubuntu-server")
        
        print(f"✅ 设备ID生成成功")
        print(f"   相同IP+主机名: {device_id_1}")
        print(f"   相同IP+主机名: {device_id_2}")
        print(f"   不同IP+主机名: {device_id_3}")
        
        if device_id_1 == device_id_2:
            print(f"   ✅ 相同IP+主机名生成相同ID")
        else:
            print(f"   ❌ 相同IP+主机名应该生成相同ID")
        
        if device_id_1 != device_id_3:
            print(f"   ✅ 不同IP生成不同ID")
        else:
            print(f"   ❌ 不同IP应该生成不同ID")
        
        print()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return
    
    # ==================== 测试2：注册新设备 ====================
    print("【测试2】注册新设备")
    print("-" * 60)
    
    try:
        device_info = device_mgr.register_device(
            hostname="test-server-01",
            ip_address="192.168.9.201",
            os_type="linux",
            os_version="Ubuntu 22.04 LTS",
            agent_version="1.0.0",
            metadata={"cpu_cores": 8, "memory_gb": 16}
        )
        
        test_device_id = device_info['device_id']
        print(f"✅ 设备注册成功")
        print(f"   设备ID: {test_device_id}")
        print(f"   设备名称: {device_info['device_name']}")
        print(f"   主机名: {device_info['hostname']}")
        print(f"   IP地址: {device_info['ip_address']}")
        print(f"   状态: {device_info['status']}")
        print()
    except Exception as e:
        print(f"❌ 注册失败: {e}")
        return
    
    # ==================== 测试3：重复注册（应该更新） ====================
    print("【测试3】重复注册（应该更新）")
    print("-" * 60)
    
    try:
        device_info_2 = device_mgr.register_device(
            hostname="test-server-01",
            ip_address="192.168.9.201",
            os_type="linux",
            os_version="Ubuntu 22.04.1 LTS",  # 版本号变化
            agent_version="1.0.1",  # Agent版本升级
            metadata={"cpu_cores": 8, "memory_gb": 32}  # 内存升级
        )
        
        if device_info_2['device_id'] == test_device_id:
            print(f"✅ 设备ID保持不变")
        else:
            print(f"❌ 设备ID不应该变化")
        
        if device_info_2['os_version'] == "Ubuntu 22.04.1 LTS":
            print(f"✅ 系统版本已更新")
        
        if device_info_2['agent_version'] == "1.0.1":
            print(f"✅ Agent版本已更新")
        
        if device_info_2['metadata']['memory_gb'] == 32:
            print(f"✅ 元数据已更新")
        
        print()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    # ==================== 测试4：获取设备详情 ====================
    print("【测试4】获取设备详情")
    print("-" * 60)
    
    try:
        device_info = device_mgr.get_device(test_device_id)
        
        if device_info:
            print(f"✅ 获取设备详情成功")
            print(f"   设备ID: {device_info['device_id']}")
            print(f"   设备名称: {device_info['device_name']}")
            print(f"   状态: {device_info['status']}")
            print()
        else:
            print(f"❌ 设备不存在")
    except Exception as e:
        print(f"❌ 获取失败: {e}")
    
    # ==================== 测试5：列出设备 ====================
    print("【测试5】列出设备")
    print("-" * 60)
    
    try:
        devices = device_mgr.list_devices(limit=10)
        print(f"✅ 列出设备成功")
        print(f"   设备数量: {len(devices)}")
        
        for device in devices[:3]:
            print(f"   - {device['device_id']}: {device['device_name']} ({device['status']})")
        
        if len(devices) > 3:
            print(f"   ... (共{len(devices)}个)")
        
        print()
    except Exception as e:
        print(f"❌ 列出失败: {e}")
    
    # ==================== 测试6：过滤在线设备 ====================
    print("【测试6】过滤在线设备")
    print("-" * 60)
    
    try:
        online_devices = device_mgr.list_devices(status="online")
        print(f"✅ 在线设备数量: {len(online_devices)}")
        print()
    except Exception as e:
        print(f"❌ 过滤失败: {e}")
    
    # ==================== 测试7：过滤Linux设备 ====================
    print("【测试7】过滤Linux设备")
    print("-" * 60)
    
    try:
        linux_devices = device_mgr.list_devices(os_type="linux")
        print(f"✅ Linux设备数量: {len(linux_devices)}")
        print()
    except Exception as e:
        print(f"❌ 过滤失败: {e}")
    
    # ==================== 测试8：更新设备信息 ====================
    print("【测试8】更新设备信息")
    print("-" * 60)
    
    try:
        updated_device = device_mgr.update_device(
            device_id=test_device_id,
            device_name="测试服务器-01",
            description="用于测试的服务器",
            tags=["test", "development"]
        )
        
        if updated_device:
            print(f"✅ 设备更新成功")
            print(f"   新名称: {updated_device['device_name']}")
            print(f"   描述: {updated_device['description']}")
            print(f"   标签: {updated_device['tags']}")
            print()
        else:
            print(f"❌ 设备不存在")
    except Exception as e:
        print(f"❌ 更新失败: {e}")
    
    # ==================== 测试9：更新设备状态 ====================
    print("【测试9】更新设备状态")
    print("-" * 60)
    
    try:
        success = device_mgr.update_device_status(test_device_id, "offline")
        
        if success:
            print(f"✅ 设备状态更新成功")
            
            # 验证状态
            device_info = device_mgr.get_device(test_device_id)
            if device_info['status'] == "offline":
                print(f"   ✅ 状态已更新为 offline")
            
            # 恢复为online
            device_mgr.update_device_status(test_device_id, "online")
            print()
        else:
            print(f"❌ 更新失败")
    except Exception as e:
        print(f"❌ 更新失败: {e}")
    
    # ==================== 测试10：获取设备数量 ====================
    print("【测试10】获取设备数量")
    print("-" * 60)
    
    try:
        total_count = device_mgr.get_device_count()
        online_count = device_mgr.get_device_count(status="online")
        linux_count = device_mgr.get_device_count(os_type="linux")
        
        print(f"✅ 设备统计:")
        print(f"   总设备数: {total_count}")
        print(f"   在线设备: {online_count}")
        print(f"   Linux设备: {linux_count}")
        print()
    except Exception as e:
        print(f"❌ 统计失败: {e}")
    
    # ==================== 测试11：删除设备 ====================
    print("【测试11】删除设备")
    print("-" * 60)
    
    try:
        deleted = device_mgr.delete_device(test_device_id)
        
        if deleted:
            print(f"✅ 设备删除成功")
            
            # 验证删除
            device_info = device_mgr.get_device(test_device_id)
            if not device_info:
                print(f"   ✅ 设备已不存在")
            else:
                print(f"   ❌ 设备仍然存在")
            print()
        else:
            print(f"❌ 设备不存在或删除失败")
    except Exception as e:
        print(f"❌ 删除失败: {e}")
    
    # ==================== 测试12：删除不存在的设备 ====================
    print("【测试12】删除不存在的设备")
    print("-" * 60)
    
    try:
        deleted = device_mgr.delete_device("device-nonexistent")
        
        if not deleted:
            print(f"✅ 正确返回False（设备不存在）")
            print()
        else:
            print(f"❌ 不应该删除成功")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_device_registration()
