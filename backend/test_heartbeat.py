"""
N8枢纽控制中心 - 心跳检测测试脚本
测试心跳检测的各个功能
"""

import time
from datetime import datetime, timedelta
from heartbeat import HeartbeatManager
from device_registration import DeviceRegistrationManager
from api_key_manager import APIKeyManager


# 数据库连接URL
DATABASE_URL = "postgresql://n8_user:n8_password_2024@192.168.9.113:14034/n8_control"


def test_heartbeat():
    """测试心跳检测"""
    
    print("=" * 60)
    print("N8 Hub Control Center - 心跳检测测试")
    print("=" * 60)
    print()
    
    # 初始化管理器
    heartbeat_mgr = HeartbeatManager(DATABASE_URL)
    device_mgr = DeviceRegistrationManager(DATABASE_URL)
    
    # ==================== 准备：创建测试设备 ====================
    print("【准备】创建测试设备")
    print("-" * 60)
    
    try:
        # 创建测试设备
        device_info = device_mgr.register_device(
            hostname="test-heartbeat-01",
            ip_address="192.168.9.210",
            os_type="linux",
            os_version="Ubuntu 22.04 LTS",
            agent_version="1.0.0"
        )
        
        test_device_id = device_info['device_id']
        print(f"✅ 测试设备创建成功")
        print(f"   设备ID: {test_device_id}")
        print()
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return
    
    # ==================== 测试1：上报心跳 ====================
    print("【测试1】上报心跳")
    print("-" * 60)
    
    try:
        heartbeat_info = heartbeat_mgr.report_heartbeat(
            device_id=test_device_id,
            metrics={
                "cpu_usage": 45.2,
                "memory_usage": 68.5,
                "disk_usage": 72.3
            },
            metadata={
                "uptime": 86400
            }
        )
        
        print(f"✅ 心跳上报成功")
        print(f"   设备ID: {heartbeat_info['device_id']}")
        print(f"   状态: {heartbeat_info['status']}")
        print(f"   最后上报: {heartbeat_info['last_seen']}")
        print(f"   下次心跳间隔: {heartbeat_info['next_heartbeat']}秒")
        print()
    except Exception as e:
        print(f"❌ 上报失败: {e}")
    
    # ==================== 测试2：获取心跳状态 ====================
    print("【测试2】获取心跳状态")
    print("-" * 60)
    
    try:
        heartbeat_status = heartbeat_mgr.get_device_heartbeat_status(test_device_id)
        
        if heartbeat_status:
            print(f"✅ 获取心跳状态成功")
            print(f"   设备ID: {heartbeat_status['device_id']}")
            print(f"   设备名称: {heartbeat_status['device_name']}")
            print(f"   状态: {heartbeat_status['status']}")
            print(f"   最后上报: {heartbeat_status['last_seen']}")
            print(f"   离线时长: {heartbeat_status['offline_duration']:.1f}秒")
            print(f"   是否超时: {heartbeat_status['is_timeout']}")
            print(f"   超时阈值: {heartbeat_status['heartbeat_timeout']}秒")
            print()
        else:
            print(f"❌ 设备不存在")
    except Exception as e:
        print(f"❌ 获取失败: {e}")
    
    # ==================== 测试3：验证设备状态为online ====================
    print("【测试3】验证设备状态为online")
    print("-" * 60)
    
    try:
        device_info = device_mgr.get_device(test_device_id)
        
        if device_info['status'] == 'online':
            print(f"✅ 设备状态正确：online")
            print()
        else:
            print(f"❌ 设备状态错误：{device_info['status']}")
    except Exception as e:
        print(f"❌ 验证失败: {e}")
    
    # ==================== 测试4：获取心跳统计 ====================
    print("【测试4】获取心跳统计")
    print("-" * 60)
    
    try:
        statistics = heartbeat_mgr.get_heartbeat_statistics()
        
        print(f"✅ 心跳统计:")
        print(f"   总设备数: {statistics['total_devices']}")
        print(f"   在线设备: {statistics['online_devices']}")
        print(f"   离线设备: {statistics['offline_devices']}")
        print(f"   最近活跃: {statistics['recent_active_devices']}")
        print(f"   超时阈值: {statistics['heartbeat_timeout']}秒")
        print()
    except Exception as e:
        print(f"❌ 获取失败: {e}")
    
    # ==================== 测试5：模拟设备离线（修改last_seen） ====================
    print("【测试5】模拟设备离线（修改last_seen）")
    print("-" * 60)
    
    try:
        # 直接修改数据库，将last_seen设置为10分钟前
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            old_time = datetime.now() - timedelta(minutes=10)
            cur.execute(
                "UPDATE devices SET last_seen = %s WHERE device_id = %s",
                (old_time, test_device_id)
            )
            conn.commit()
        conn.close()
        
        print(f"✅ 已将设备last_seen修改为10分钟前")
        print()
    except Exception as e:
        print(f"❌ 修改失败: {e}")
    
    # ==================== 测试6：检查离线设备 ====================
    print("【测试6】检查离线设备")
    print("-" * 60)
    
    try:
        offline_devices = heartbeat_mgr.check_offline_devices()
        
        print(f"✅ 离线检测完成")
        print(f"   离线设备数: {len(offline_devices)}")
        
        if test_device_id in offline_devices:
            print(f"   ✅ 测试设备已被标记为离线")
        else:
            print(f"   ⚠️ 测试设备未被标记为离线")
        
        print()
    except Exception as e:
        print(f"❌ 检测失败: {e}")
    
    # ==================== 测试7：验证设备状态为offline ====================
    print("【测试7】验证设备状态为offline")
    print("-" * 60)
    
    try:
        device_info = device_mgr.get_device(test_device_id)
        
        if device_info['status'] == 'offline':
            print(f"✅ 设备状态正确：offline")
            print()
        else:
            print(f"❌ 设备状态错误：{device_info['status']}")
    except Exception as e:
        print(f"❌ 验证失败: {e}")
    
    # ==================== 测试8：再次上报心跳（应该恢复online） ====================
    print("【测试8】再次上报心跳（应该恢复online）")
    print("-" * 60)
    
    try:
        heartbeat_info = heartbeat_mgr.report_heartbeat(
            device_id=test_device_id,
            metrics={
                "cpu_usage": 50.0,
                "memory_usage": 70.0,
                "disk_usage": 75.0
            }
        )
        
        print(f"✅ 心跳上报成功")
        print(f"   状态: {heartbeat_info['status']}")
        
        # 验证状态
        device_info = device_mgr.get_device(test_device_id)
        if device_info['status'] == 'online':
            print(f"   ✅ 设备状态已恢复为 online")
        else:
            print(f"   ❌ 设备状态未恢复: {device_info['status']}")
        
        print()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    # ==================== 测试9：上报不存在的设备（应该失败） ====================
    print("【测试9】上报不存在的设备（应该失败）")
    print("-" * 60)
    
    try:
        heartbeat_mgr.report_heartbeat(
            device_id="device-nonexistent",
            metrics={}
        )
        print(f"❌ 不应该成功")
    except ValueError as e:
        print(f"✅ 正确抛出异常: {e}")
        print()
    except Exception as e:
        print(f"❌ 异常类型错误: {e}")
    
    # ==================== 测试10：获取不存在设备的心跳状态 ====================
    print("【测试10】获取不存在设备的心跳状态")
    print("-" * 60)
    
    try:
        heartbeat_status = heartbeat_mgr.get_device_heartbeat_status("device-nonexistent")
        
        if heartbeat_status is None:
            print(f"✅ 正确返回None（设备不存在）")
            print()
        else:
            print(f"❌ 不应该返回数据")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    # ==================== 测试11：验证指标已保存到元数据 ====================
    print("【测试11】验证指标已保存到元数据")
    print("-" * 60)
    
    try:
        device_info = device_mgr.get_device(test_device_id)
        metadata = device_info.get('metadata', {})
        metrics = metadata.get('metrics', {})
        
        if metrics:
            print(f"✅ 指标已保存到元数据:")
            print(f"   CPU使用率: {metrics.get('cpu_usage')}%")
            print(f"   内存使用率: {metrics.get('memory_usage')}%")
            print(f"   磁盘使用率: {metrics.get('disk_usage')}%")
            print(f"   更新时间: {metadata.get('metrics_updated_at')}")
            print()
        else:
            print(f"⚠️ 元数据中未找到指标")
    except Exception as e:
        print(f"❌ 验证失败: {e}")
    
    # ==================== 清理：删除测试设备 ====================
    print("【清理】删除测试设备")
    print("-" * 60)
    
    try:
        deleted = device_mgr.delete_device(test_device_id)
        
        if deleted:
            print(f"✅ 测试设备已删除")
            print()
        else:
            print(f"❌ 删除失败")
    except Exception as e:
        print(f"❌ 删除失败: {e}")
    
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_heartbeat()
