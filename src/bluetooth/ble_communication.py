# BLE通信实现 
import asyncio
from bleak import BleakScanner, BleakClient

# 固定特征UUID
APP_CHARACTERISTIC_UUID = "00002c10-0000-1000-8000-00805f9b34fb"

# 设备发现与连接
async def discover_devices():
    """扫描附近的蓝牙设备并返回设备列表。"""
    devices = await BleakScanner.discover()
    return devices

async def connect_to_device(address):
    """连接到指定地址的蓝牙设备，并保持连接状态。"""
    client = BleakClient(address)
    await client.connect()
    if client.is_connected:
        print(f"成功连接到设备: {address}")
        return client
    else:
        print(f"无法连接到设备: {address}")
        return None

# 发送和接收AT命令
async def send_command(client, command, char_uuid=None, max_retries=3):
    """通过BLE发送AT命令并接收响应。
    
    :param client: BLE客户端对象
    :param command: 要发送的命令字符串
    :param char_uuid: 可选。指定写入/通知的特征UUID，默认使用APP特征
    :param max_retries: 最大重试次数，默认为3
    """
    if client is None or not client.is_connected:
        print("设备未连接，无法发送命令")
        return None
        
    # 使用特征UUID
    if char_uuid is None:
        char_uuid = APP_CHARACTERISTIC_UUID
        
    for attempt in range(max_retries):
        try:
            # 确保服务发现已经完成
            await client.get_services()

            # 创建一个 Future，用于等待通知返回
            loop = asyncio.get_running_loop()
            response_future = loop.create_future()

            # 通知回调函数
            def notification_handler(sender, data):
                try:
                    result = data.decode()
                except UnicodeDecodeError:
                    result = data.hex()
                print(f"收到通知: {result}")
                if not response_future.done():
                    response_future.set_result(result)

            # 准备命令，确保以$\r\n结尾
            command = command.rstrip("\r\n").rstrip("$") + "$\r\n"

            # 启动通知并发送命令
            await client.start_notify(char_uuid, notification_handler)            
            print(f"发送命令: {command.strip()}")
            await client.write_gatt_char(char_uuid, command.encode(), response=True)
            
            # 等待响应
            await asyncio.sleep(3.0)
            try:
                response = await asyncio.wait_for(response_future, timeout=15.0)
                await client.stop_notify(char_uuid)
                return response
            except asyncio.TimeoutError:
                await client.stop_notify(char_uuid)
                print(f"第{attempt+1}次尝试超时")
        except Exception as e:
            print(f"第{attempt+1}次尝试失败: {e}")
            await asyncio.sleep(1.0)
    
    print("所有重试均失败")
    return None 