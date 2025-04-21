"""
滑板车控制器，整合蓝牙和MQTT控制功能
"""
import sys
import os
import asyncio
from datetime import datetime

# 将项目根目录添加到Python搜索路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.bluetooth.ble_communication import discover_devices, connect_to_device, send_command
from src.mqtt.lock_controller import MQTTLockController
from src.database.models import Database, ScooterManager, LockManager

class ScooterController:
    """
    滑板车控制器类，整合车辆和锁的控制
    """
    
    def __init__(self):
        # 初始化数据库
        self.db = Database()
        self.scooter_manager = ScooterManager(self.db)
        self.lock_manager = LockManager(self.db)
        
        # 初始化MQTT控制器
        self.mqtt_controller = MQTTLockController()
        
        # 存储已连接的设备客户端
        self.connected_clients = {}
    
    async def scan_scooters(self):
        """
        扫描附近的蓝牙设备，并与数据库中的记录匹配
        
        Returns:
            list: 匹配到的车辆列表
        """
        try:
            # 扫描蓝牙设备
            devices = await discover_devices()
            
            # 获取数据库中所有车辆
            db_scooters = self.scooter_manager.get_all_scooters()
            db_addresses = {scooter['bluetooth_address']: scooter for scooter in db_scooters}
            
            # 匹配蓝牙设备和数据库记录
            matched_scooters = []
            for device in devices:
                if device.address in db_addresses:
                    scooter_info = db_addresses[device.address]
                    matched_scooters.append({
                        "device": device,
                        "scooter_id": scooter_info['scooter_id'],
                        "scooter_name": scooter_info['scooter_name'],
                        "status": scooter_info['status'],
                        "lock_controller_id": scooter_info['lock_controller_id'],
                        "sub_lock_number": scooter_info['sub_lock_number']
                    })
                else:
                    # 未知设备，仅保留蓝牙信息
                    matched_scooters.append({
                        "device": device,
                        "scooter_id": None,
                        "scooter_name": device.name if device.name else "未知设备",
                        "status": "未注册",
                        "lock_controller_id": None,
                        "sub_lock_number": None
                    })
            
            return matched_scooters
            
        except Exception as e:
            print(f"扫描车辆时出错: {e}")
            return []
    
    async def connect_scooter(self, device):
        """
        连接到指定的蓝牙设备
        
        Args:
            device: 蓝牙设备对象
            
        Returns:
            client: 连接的客户端对象，失败则返回None
        """
        try:
            client = await connect_to_device(device.address)
            if client and client.is_connected:
                self.connected_clients[device.address] = client
                return client
            return None
        except Exception as e:
            print(f"连接车辆时出错: {e}")
            return None
    
    async def unlock_scooter(self, scooter_id, ble_password):
        """
        解锁车辆和对应的锁
        
        Args:
            scooter_id (str): 车辆ID
            ble_password (str): 蓝牙密码
            
        Returns:
            tuple: (蓝牙解锁结果, MQTT解锁结果)
        """
        try:
            # 获取车辆信息
            scooter_info = self.scooter_manager.get_scooter(scooter_id=scooter_id)
            if not scooter_info:
                print(f"找不到车辆信息: {scooter_id}")
                return False, False
            
            # 检查是否有连接的客户端
            client = self.connected_clients.get(scooter_info['bluetooth_address'])
            if not client or not client.is_connected:
                # 尝试连接
                device_info = {"address": scooter_info['bluetooth_address']}
                type("BluetoothDevice", (), device_info)  # 创建一个简单的设备对象
                client = await self.connect_scooter(device_info)
                if not client:
                    print(f"无法连接到车辆: {scooter_id}")
                    return False, False
            
            # 通过蓝牙解锁车辆 (ECU解锁)
            command = f"AT+BKSCT={ble_password},0"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
            ble_result = await send_command(client, command, char_uuid)
            ble_success = ble_result is not None
            
            # 通过MQTT解锁车锁
            mqtt_success = False
            if scooter_info['lock_controller_id'] and scooter_info['sub_lock_number']:
                mqtt_success = await self.mqtt_controller.async_unlock(
                    scooter_info['lock_controller_id'], 
                    scooter_info['sub_lock_number']
                )
            
            # 记录操作日志
            if ble_success or mqtt_success:
                self.lock_manager.log_operation(
                    scooter_id,
                    scooter_info['lock_controller_id'],
                    scooter_info['sub_lock_number'],
                    "解锁",
                    "成功" if (ble_success and mqtt_success) else "部分成功"
                )
                
                # 更新车辆状态
                self.scooter_manager.update_scooter_status(scooter_id, "使用中")
            
            return ble_success, mqtt_success
            
        except Exception as e:
            print(f"解锁车辆时出错: {e}")
            return False, False
    
    async def lock_scooter(self, scooter_id, ble_password):
        """
        锁定车辆和对应的锁
        
        Args:
            scooter_id (str): 车辆ID
            ble_password (str): 蓝牙密码
            
        Returns:
            tuple: (蓝牙锁定结果, MQTT锁定结果)
        """
        try:
            # 获取车辆信息
            scooter_info = self.scooter_manager.get_scooter(scooter_id=scooter_id)
            if not scooter_info:
                print(f"找不到车辆信息: {scooter_id}")
                return False, False
            
            # 检查是否有连接的客户端
            client = self.connected_clients.get(scooter_info['bluetooth_address'])
            if not client or not client.is_connected:
                # 尝试连接
                device_info = {"address": scooter_info['bluetooth_address']}
                type("BluetoothDevice", (), device_info)  # 创建一个简单的设备对象
                client = await self.connect_scooter(device_info)
                if not client:
                    print(f"无法连接到车辆: {scooter_id}")
                    return False, False
            
            # 通过蓝牙锁定车辆 (ECU上锁)
            command = f"AT+BKSCT={ble_password},1"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
            ble_result = await send_command(client, command, char_uuid)
            ble_success = ble_result is not None
            
            # 记录操作日志
            self.lock_manager.log_operation(
                scooter_id,
                scooter_info['lock_controller_id'],
                scooter_info['sub_lock_number'],
                "锁定",
                "成功" if ble_success else "失败"
            )
            
            # 更新车辆状态
            if ble_success:
                self.scooter_manager.update_scooter_status(scooter_id, "空闲")
            
            return ble_success, True  # 第二个参数暂时返回True，因为MQTT没有锁定操作
            
        except Exception as e:
            print(f"锁定车辆时出错: {e}")
            return False, False
    
    def register_scooter(self, scooter_id, scooter_name, bluetooth_address, lock_controller_id=None, sub_lock_number=None):
        """
        注册新车辆
        
        Args:
            scooter_id (str): 车辆ID
            scooter_name (str): 车辆名称
            bluetooth_address (str): 蓝牙地址
            lock_controller_id (str, optional): 锁控制器ID
            sub_lock_number (int, optional): 子锁号码
            
        Returns:
            bool: 是否注册成功
        """
        return self.scooter_manager.add_scooter(
            scooter_id, scooter_name, bluetooth_address, lock_controller_id, sub_lock_number
        )
    
    def register_lock_controller(self, controller_id, controller_name, mqtt_topic_prefix):
        """
        注册新的锁控制器
        
        Args:
            controller_id (str): 控制器ID
            controller_name (str): 控制器名称
            mqtt_topic_prefix (str): MQTT主题前缀
            
        Returns:
            bool: 是否注册成功
        """
        return self.lock_manager.add_lock_controller(controller_id, controller_name, mqtt_topic_prefix)
    
    def update_scooter_lock_association(self, scooter_id, lock_controller_id, sub_lock_number):
        """
        更新车辆和锁的关联关系
        
        Args:
            scooter_id (str): 车辆ID
            lock_controller_id (str): 锁控制器ID
            sub_lock_number (int): 子锁号码
            
        Returns:
            bool: 是否更新成功
        """
        return self.scooter_manager.update_scooter_lock(scooter_id, lock_controller_id, sub_lock_number)
    
    def get_operation_logs(self, scooter_id=None, limit=50):
        """
        获取操作日志
        
        Args:
            scooter_id (str, optional): 车辆ID，如果不提供则获取所有车辆的日志
            limit (int, optional): 最大记录数，默认50条
            
        Returns:
            list: 操作日志列表
        """
        query = f"SELECT * FROM operation_logs"
        params = []
        
        if scooter_id:
            query += " WHERE scooter_id = ?"
            params.append(scooter_id)
        
        query += " ORDER BY operation_time DESC LIMIT ?"
        params.append(limit)
        
        self.db.cursor.execute(query, params)
        return [dict(row) for row in self.db.cursor.fetchall()] 