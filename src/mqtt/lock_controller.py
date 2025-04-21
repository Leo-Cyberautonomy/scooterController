"""
MQTT锁控制器实现
"""
import json
import subprocess
import os
import platform
import asyncio

class MQTTLockController:
    """
    使用MQTT协议控制车锁
    """
    
    def __init__(self, mqtt_host="mqtt.xcubesports.com.cn", mqtt_user="myuser", mqtt_password="kejin"):
        """初始化MQTT控制器"""
        self.mqtt_host = mqtt_host
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
    
    def unlock(self, controller_id, sub_lock_number=1):
        """
        解锁指定控制器的指定子锁
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int, optional): 子锁号码，默认为1
            
        Returns:
            bool: 操作是否成功
        """
        return self._send_command("ULC" + controller_id, {"taskId": 1, "payload": {"SLN": sub_lock_number}})
    
    def query_status(self, controller_id, sub_lock_number=1):
        """
        查询指定控制器的指定子锁状态
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int, optional): 子锁号码，默认为1
            
        Returns:
            bool: 操作是否成功
        """
        return self._send_command("QRY" + controller_id, {"taskId": 2, "payload": {"SLN": sub_lock_number}})
    
    def _send_command(self, topic, payload):
        """
        发送MQTT命令
        
        Args:
            topic (str): MQTT主题
            payload (dict): 命令载荷
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 将字典转换为JSON字符串
            payload_str = json.dumps(payload)
            
            # 构建MQTT发布命令
            command = [
                "mosquitto_pub", 
                "-h", self.mqtt_host,
                "-t", topic,
                "-u", self.mqtt_user,
                "-P", self.mqtt_password,
                "-m", payload_str
            ]
            
            # 执行命令
            result = subprocess.run(command, capture_output=True, text=True)
            
            # 检查命令是否成功执行
            if result.returncode == 0:
                print(f"MQTT命令发送成功: {topic} - {payload_str}")
                return True
            else:
                print(f"MQTT命令发送失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"发送MQTT命令时出错: {e}")
            return False

    async def async_unlock(self, controller_id, sub_lock_number=1):
        """
        异步解锁指定控制器的指定子锁
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int, optional): 子锁号码，默认为1
            
        Returns:
            bool: 操作是否成功
        """
        return await self._async_send_command("ULC" + controller_id, {"taskId": 1, "payload": {"SLN": sub_lock_number}})
    
    async def async_query_status(self, controller_id, sub_lock_number=1):
        """
        异步查询指定控制器的指定子锁状态
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int, optional): 子锁号码，默认为1
            
        Returns:
            bool: 操作是否成功
        """
        return await self._async_send_command("QRY" + controller_id, {"taskId": 2, "payload": {"SLN": sub_lock_number}})
    
    async def _async_send_command(self, topic, payload):
        """
        异步发送MQTT命令
        
        Args:
            topic (str): MQTT主题
            payload (dict): 命令载荷
            
        Returns:
            bool: 操作是否成功
        """
        # 将同步方法包装为异步方法
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._send_command, topic, payload) 