import asyncio
from typing import List, Optional, Dict, Any
from bleak import BleakScanner, BleakClient, BLEDevice
from logger import get_logger

# 创建日志记录器
logger = get_logger('ble_model')

class BLEModel:
    """蓝牙模型类，封装所有蓝牙操作功能"""
    
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.connected_device: Optional[BLEDevice] = None
        self._scan_results: List[BLEDevice] = []
        
        # 定义特征UUID
        self.APP_CHARACTERISTIC_UUID = "00002c10-0000-1000-8000-00805f9b34fb"


    async def scan_devices(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """
        扫描附近的蓝牙设备，只保留名称为"zk301"的设备
        
        Args:
            timeout: 扫描超时时间（秒）
            
        Returns:
            设备信息列表，每个设备包含名称、地址和信号强度
        """
        logger.info(f"开始扫描蓝牙设备，超时时间: {timeout}秒")
        all_devices = await BleakScanner.discover()
        
        # 只保留名称为"zk301"的设备
        self._scan_results = [device for device in all_devices if device.name and device.name.strip() == "zk301"]
        
        devices_info = []
        for device in self._scan_results:
            device_info = {
                "name": device.name,
                "address": device.address,
                "rssi": device.rssi,
                "metadata": device.metadata
            }
            devices_info.append(device_info)
            logger.info(f"发现zk301设备: {device_info['name']} ({device_info['address']})")
        
        if not devices_info:
            logger.info("未发现zk301设备")
        
        return devices_info

    async def connect(self, address: str) -> bool:
        """
        连接到指定的蓝牙设备
        
        Args:
            address: 设备地址
            
        Returns:
            连接是否成功
        """
        try:
            self.client = BleakClient(address)
            await self.client.connect()
            
            if self.client and self.client.is_connected:
                # 查找对应的设备信息
                for device in self._scan_results:
                    if device.address == address:
                        self.connected_device = device
                        break
                logger.info(f"成功连接到设备: {address}")
                return True
            return False
        except Exception as e:
            logger.error(f"连接设备失败: {e}")
            return False

    async def disconnect(self):
        """断开当前连接的设备"""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            self.client = None
            self.connected_device = None
            logger.info("已断开设备连接")

    async def send_command(self, command: str, char_uuid: str = None, max_retries: int = 3) -> Optional[str]:
        """
        发送命令并接收响应
        
        Args:
            command: 要发送的命令字符串
            char_uuid: 特征UUID，默认使用APP特征
            max_retries: 最大重试次数
            
        Returns:
            设备返回的响应
        """
        if not self.client or not self.client.is_connected:
            logger.warning("设备未连接，无法发送命令")
            return None
            
        if char_uuid is None:
            char_uuid = self.APP_CHARACTERISTIC_UUID
            
        for attempt in range(max_retries):
            try:
                # 确保服务发现已经完成
                await self.client.get_services()

                # 创建一个 Future，用于等待通知返回
                loop = asyncio.get_running_loop()
                response_future = loop.create_future()

                # 通知回调函数
                def notification_handler(sender, data):
                    try:
                        result = data.decode()
                    except UnicodeDecodeError:
                        result = data.hex()
                    logger.debug(f"收到通知: {result}")
                    if not response_future.done():
                        response_future.set_result(result)

                # 准备命令，确保以$\r\n结尾
                command = command.rstrip("\r\n").rstrip("$") + "$\r\n"

                # 启动通知并发送命令
                await self.client.start_notify(char_uuid, notification_handler)            
                logger.info(f"发送命令: {command.strip()}")
                await self.client.write_gatt_char(char_uuid, command.encode(), response=True)
                
                # 等待响应
                try:
                    response = await asyncio.wait_for(response_future, timeout=15.0)
                    await self.client.stop_notify(char_uuid)
                    return response
                except asyncio.TimeoutError:
                    await self.client.stop_notify(char_uuid)
                    logger.warning(f"第{attempt+1}次尝试超时")
            except Exception as e:
                logger.error(f"第{attempt+1}次尝试失败: {e}")
                await asyncio.sleep(1.0)
        
        logger.error("所有重试均失败")
        return None

    # 设备控制命令
    async def lock_device(self, password: str) -> Optional[str]:
        """锁定设备"""
        command = f"AT+BKSCT={password},1"
        return await self.send_command(command)

    async def unlock_device(self, password: str) -> Optional[str]:
        """解锁设备"""
        command = f"AT+BKSCT={password},0"
        return await self.send_command(command)

    async def toggle_headlight(self, password: str, status: int) -> Optional[str]:
        """
        控制头灯状态
        
        Args:
            status: 头灯状态，0表示关闭，1表示开启
            
        Returns:
            操作结果，0表示失败，1表示成功
        """
        command = f"AT+BKLED={password},0,{status}"
        return await self.send_command(command)

    async def get_device_info(self, password: str) -> Optional[str]:
        """获取设备信息"""
        command = f"AT+BKINF={password},0"
        return await self.send_command(command)

    async def get_headlight_status(self, password: str) -> Optional[str]:
        """
        获取头灯状态
        
        Args:
            password: 设备密码
            
        Returns:
            头灯状态信息
        """
        # 通过获取设备信息来获取头灯状态
        info = await self.get_device_info(password)
        if info:
            # 解析设备信息中的头灯状态
            # 格式: +ACK:BKINF,<Lock Status>,<Scooter Speed>,<Current Mileage>,<Total Mileage>,<Ride Time>,<Scooter Battery Percentage>,<Headlamp Status>
            parts = info.split(",")
            if len(parts) >= 7:
                headlamp_status = parts[6].strip()
                return "开启" if headlamp_status == "1" else "关闭"
        return None

    async def send_warning(self, password: str) -> Optional[str]:
        """发送警告"""
        command = f"AT+BKWRN={password},0"
        return await self.send_command(command)

    @property
    def is_connected(self) -> bool:
        """检查设备是否已连接"""
        return self.client is not None and self.client.is_connected

    @property
    def connected_device_info(self) -> Optional[Dict[str, Any]]:
        """获取当前连接设备的信息"""
        if self.connected_device:
            return {
                "name": self.connected_device.name or "未知设备",
                "address": self.connected_device.address,
                "rssi": self.connected_device.rssi,
                "metadata": self.connected_device.metadata
            }
        return None 