"""
滑板车控制器，整合蓝牙和MQTT控制功能
"""
import sys
import os
import asyncio
from datetime import datetime
import json

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
        
        # 定义锁控制器映射关系
        self.controller_mapping = {
            # 锁1-5对应第一个控制器
            1: {"controller_id": "866846061120977", "sub_lock_number": 1},
            2: {"controller_id": "866846061120977", "sub_lock_number": 2},
            3: {"controller_id": "866846061120977", "sub_lock_number": 3},
            4: {"controller_id": "866846061120977", "sub_lock_number": 4},
            5: {"controller_id": "866846061120977", "sub_lock_number": 5},
            # 锁6-10对应第二个控制器
            6: {"controller_id": "866846061051685", "sub_lock_number": 1},
            7: {"controller_id": "866846061051685", "sub_lock_number": 2},
            8: {"controller_id": "866846061051685", "sub_lock_number": 3},
            9: {"controller_id": "866846061051685", "sub_lock_number": 4},
            10: {"controller_id": "866846061051685", "sub_lock_number": 5}
        }
        
        # 启用自动更新车辆和锁的关联关系
        self.enable_auto_association_update()
    
    def __del__(self):
        """确保在对象销毁时关闭数据库和MQTT连接"""
        try:
            # 关闭MQTT连接
            if hasattr(self, 'mqtt_controller'):
                self.mqtt_controller.close()
                
            # 关闭数据库连接
            if hasattr(self, 'db'):
                self.db.close()
        except Exception as e:
            print(f"关闭资源时出错: {e}")
    
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
            
            # 1. 先通过蓝牙解锁车辆 (ECU解锁)
            ble_success = False
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
            
            command = f"AT+BKSCT={ble_password},0"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
            ble_result = await send_command(client, command, char_uuid)
            ble_success = ble_result is not None
            
            # 给ECU一些时间解锁
            if ble_success:
                await asyncio.sleep(1.0)
            
            # 2. 再通过MQTT解锁物理锁
            mqtt_success = False
            
            # 首先检查车辆是否有直接关联的锁控制器
            if scooter_info['lock_controller_id'] and scooter_info['sub_lock_number']:
                print(f"使用车辆关联的锁: 控制器={scooter_info['lock_controller_id']}, 子锁号={scooter_info['sub_lock_number']}")
                # 直接使用关联的锁控制器
                controller_id = scooter_info['lock_controller_id']
                sub_lock_number = scooter_info['sub_lock_number']
                
                # 直接使用同步方法解锁
                mqtt_success = self.mqtt_controller.unlock(controller_id, sub_lock_number)
            else:
                # 车辆没有关联锁信息，使用硬编码的第一个映射（备用方案）
                print(f"车辆 {scooter_id} 未关联锁控制器，使用默认锁")
                lock_number = 1  # 使用第一个锁为例
                controller_info = self.controller_mapping.get(lock_number)
                if controller_info:
                    print(f"使用默认锁: 控制器={controller_info['controller_id']}, 子锁号={controller_info['sub_lock_number']}")
                    mqtt_success = self.mqtt_controller.unlock(
                        controller_info['controller_id'], 
                        controller_info['sub_lock_number']
                    )
            
            # 记录操作日志
            if ble_success or mqtt_success:
                # 使用实际的控制器ID和子锁号记录日志
                controller_id = scooter_info['lock_controller_id']
                sub_lock_number = scooter_info['sub_lock_number']
                
                if not controller_id or not sub_lock_number:
                    # 如果车辆没有关联锁，使用使用的默认锁
                    controller_info = self.controller_mapping.get(1)
                    if controller_info:
                        controller_id = controller_info['controller_id']
                        sub_lock_number = controller_info['sub_lock_number']
                
                self.lock_manager.log_operation(
                    scooter_id,
                    controller_id,
                    sub_lock_number,
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
        success = self.scooter_manager.update_scooter_lock(scooter_id, lock_controller_id, sub_lock_number)
        
        # 记录操作日志
        if success:
            self.lock_manager.log_operation(
                scooter_id,
                lock_controller_id,
                sub_lock_number,
                "更新关联",
                "成功"
            )
            
        return success
    
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
    
    def enable_auto_association_update(self):
        """启用自动更新车辆和锁的关联关系，通过监听MQTT的data_report消息"""
        # 订阅data_report主题并设置回调函数
        self.mqtt_controller.subscribe_data_report(self.handle_data_report)
        print("已启用自动更新车辆和锁的关联关系功能")
    
    def get_lock_number(self, controller_id, sub_lock_number):
        """
        根据控制器ID和子锁号获取对应的锁编号(1-10)
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int): 子锁号
            
        Returns:
            int: 锁编号(1-10)，如果找不到对应关系则返回None
        """
        try:
            sub_lock_number = int(sub_lock_number)
            # 逆向查找映射关系
            for lock_number, info in self.controller_mapping.items():
                if (info["controller_id"] == controller_id and 
                    info["sub_lock_number"] == sub_lock_number):
                    return lock_number
            return None
        except (ValueError, TypeError):
            print(f"无效的子锁号: {sub_lock_number}")
            return None
    
    def handle_data_report(self, topic, payload_str):
        """
        处理data_report主题的消息，自动更新车辆和锁的关联关系
        
        Args:
            topic (str): 消息主题
            payload_str (str): 消息内容（JSON字符串）
        """
        try:
            # 解析JSON数据
            payload = json.loads(payload_str)
            
            # 检查必要的字段是否存在
            if 'state' not in payload or 'SN' not in payload:
                print("消息格式不正确，缺少必要字段")
                return
            
            # 提取关键信息
            state = payload.get('state')
            sn = payload.get('SN')
            seq = payload.get('seq', 0)
            battery_level = payload.get('batteryLevel', 0)
            signal_strength = payload.get('signalStrength', 0)
            no = payload.get('NO', '')
            open_type = payload.get('openType', -1)
            timestamp = datetime.now().isoformat()
            
            # 记录接收到的数据报告
            print(f"接收到数据报告：序列号={seq}, 状态={state}, SN={sn}, 开关类型={open_type}")
            
            # 只处理关锁状态的消息（state='1'代表锁处在关闭状态）
            if state != '1':
                if state == '0':
                    print(f"锁已打开，openType={open_type}")
                return
                
            # 从SN中提取锁号和共享物品ID
            if len(sn) >= 16:
                lock_controller_id = sn[1:4]  # 第2~4位为卡槽号/锁号
                item_id = sn[4:16]     # 第5~16位表示插销ID/共享物品的ID
                raw_sub_lock_number = int(item_id[-1]) if item_id[-1].isdigit() else 1  # 最后一位表示共享品种类
                
                # 使用控制器ID和子锁号映射到锁编号(1-10)
                # 注意：这里我们尝试查找真实控制器ID，但如果控制器ID只是"002"这样的编号，
                # 我们需要将其映射到我们定义的控制器ID
                real_controller_id = None
                if lock_controller_id == "002":  # 示例：如果SN中的锁号是"002"
                    real_controller_id = "866846061120977"  # 映射到实际控制器ID
                elif lock_controller_id == "003":  # 示例：如果SN中的锁号是"003"
                    real_controller_id = "866846061051685"  # 映射到实际控制器ID
                else:
                    # 尝试使用SN中的锁号作为实际控制器ID
                    real_controller_id = lock_controller_id
                
                # 使用原始子锁号计算锁编号
                lock_number = None
                # 检查是否为正常的控制器ID
                if real_controller_id == "866846061120977":
                    # 第一个控制器，锁编号为1-5
                    lock_number = raw_sub_lock_number  # 直接使用子锁号作为锁编号
                elif real_controller_id == "866846061051685":
                    # 第二个控制器，锁编号为6-10
                    lock_number = raw_sub_lock_number + 5  # 子锁号+5作为锁编号
                else:
                    # 尝试从映射中找到对应关系
                    lock_number = self.get_lock_number(real_controller_id, raw_sub_lock_number)
                
                print(f"控制器ID: {real_controller_id}, 子锁号: {raw_sub_lock_number}, 映射到锁编号: {lock_number}")
                
                # 如果是正常还车（openType == 1），则进行关联更新
                if open_type == 1 and lock_number is not None:
                    print(f"检测到正常还车，锁编号={lock_number}")
                    
                    # 查询最近锁定的车辆（通过操作日志）
                    recent_lock_logs = self.get_recent_lock_operations(limit=10)
                    
                    for log in recent_lock_logs:
                        # 检查时间间隔是否在合理范围内（例如5分钟内）
                        log_time = datetime.fromisoformat(log['operation_time'])
                        current_time = datetime.fromisoformat(timestamp)
                        time_diff = (current_time - log_time).total_seconds()
                        
                        # 如果时间间隔在5分钟内且操作类型为"锁定"
                        if time_diff <= 300 and log['operation_type'] == "锁定":
                            scooter_id = log['scooter_id']
                            
                            # 更新车辆和锁关联关系 - 使用锁编号(1-10)
                            success = self.update_scooter_lock_association(
                                scooter_id, real_controller_id, lock_number
                            )
                            
                            if success:
                                print(f"已自动更新车辆 {scooter_id} 的锁关联关系：锁编号={lock_number}")
                            else:
                                print(f"自动更新车辆 {scooter_id} 的锁关联关系失败")
                            
                            # 更新成功后退出循环
                            break
                else:
                    print(f"非正常还车或无法找到锁编号映射，openType={open_type}, lockNumber={lock_number}")
        
        except json.JSONDecodeError:
            print("JSON解析失败")
        except Exception as e:
            print(f"处理data_report消息时出错: {e}")
    
    def get_recent_lock_operations(self, limit=10):
        """
        获取最近的锁定操作记录
        
        Args:
            limit (int): 最大记录数，默认10条
            
        Returns:
            list: 操作日志列表
        """
        query = "SELECT * FROM operation_logs WHERE operation_type = '锁定' ORDER BY operation_time DESC LIMIT ?"
        self.db.cursor.execute(query, (limit,))
        return [dict(row) for row in self.db.cursor.fetchall()]
    
    def get_controller_info(self, lock_number):
        """
        根据锁编号(1-10)获取对应的控制器ID和子锁号
        
        Args:
            lock_number (int): 锁编号(1-10)
            
        Returns:
            dict: 包含controller_id和sub_lock_number的字典，如果找不到对应关系则返回None
        """
        try:
            lock_number = int(lock_number)
            return self.controller_mapping.get(lock_number)
        except (ValueError, TypeError):
            print(f"无效的锁编号: {lock_number}")
            return None 