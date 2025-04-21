# BLE通信实现 
import asyncio
from bleak import BleakScanner, BleakClient

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
async def send_command(client, command, char_uuid=None):
    """通过BLE发送AT命令并接收响应。
    
    :param client: BLE客户端对象
    :param command: 要发送的命令字符串
    :param char_uuid: 可选。指定写入/通知的特征UUID，
                      如果为None，则默认使用 Control 特征 UUID 00002c01-0000-1000-8000-00805f9b34fb
    """
    try:
        # 确保服务发现已经完成
        await client.get_services()

        if char_uuid is None:
            char_uuid = "00002c01-0000-1000-8000-00805f9b34fb"

        # 创建一个 Future，用于等待通知返回
        loop = asyncio.get_running_loop()
        response_future = loop.create_future()

        # 通知回调函数，收到数据后设置 Future 的结果
        def notification_handler(sender, data):
            try:
                result = data.decode()
            except UnicodeDecodeError:
                result = data.hex()
            print(f"收到通知: {result}")   # 调试输出
            if not response_future.done():
                response_future.set_result(result)

        # 确保命令以 \r\n 结尾（文档A要求每条消息以CR+LF结尾）
        if not command.endswith("\r\n"):
            command += "\r\n"

        # 启动通知订阅
        await client.start_notify(char_uuid, notification_handler)

        # 发送命令
        print(f"发送命令: {command.strip()} 到特征 {char_uuid}")   # 调试输出
        await client.write_gatt_char(char_uuid, command.encode())
        # 添加延时，给予设备更多时间处理命令并发送通知
        await asyncio.sleep(1.5)

        # 等待通知返回结果，超时设置为 15 秒
        response = await asyncio.wait_for(response_future, timeout=15.0)

        # 停止通知
        await client.stop_notify(char_uuid)

        return response
    except asyncio.TimeoutError:
        print("发送命令时超时: 未收到响应")
        return None
    except Exception as e:
        print(f"发送命令时出错: {e}")
        return None 