"""
MQTT锁控制器实现 - 使用paho-mqtt库
"""
import json
import asyncio
import threading
import time
import paho.mqtt.client as mqtt
from queue import Queue, Empty

class MQTTLockController:
    """
    使用MQTT协议控制车锁，基于paho-mqtt库
    """
    
    def __init__(self, mqtt_host="mqtt.xcubesports.com.cn", mqtt_user="myuser", mqtt_password="kejin", mqtt_port=1883):
        """初始化MQTT控制器"""
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.client = None
        self.connected = False
        self.response_queue = Queue()
        self.subscribed_topics = set()
        
        # 创建客户端并初始化连接
        self._init_client()
    
    def _init_client(self):
        """初始化MQTT客户端和连接"""
        # 创建客户端
        client_id = f"scooter_controller_{int(time.time())}"
        self.client = mqtt.Client(client_id=client_id)
        
        # 设置认证信息
        self.client.username_pw_set(self.mqtt_user, self.mqtt_password)
        
        # 设置回调函数
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # 启动连接线程
        self._connect()
    
    def _connect(self):
        """连接到MQTT服务器"""
        try:
            self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            # 启动后台线程处理网络流量
            self.client.loop_start()
            print(f"正在连接到MQTT服务器: {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            print(f"MQTT连接失败: {e}")
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """连接建立回调函数"""
        if rc == 0:
            print("MQTT连接成功")
            self.connected = True
        else:
            print(f"MQTT连接失败，返回码: {rc}")
            self.connected = False
    
    def _on_message(self, client, userdata, msg):
        """消息接收回调函数"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            print(f"收到MQTT消息: 主题={topic}, 内容={payload}")
            # 将响应放入队列
            self.response_queue.put((topic, payload))
        except Exception as e:
            print(f"处理MQTT消息时出错: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调函数"""
        print(f"MQTT连接断开, 返回码: {rc}")
        self.connected = False
        if rc != 0:
            print("尝试重新连接...")
            self._connect()
    
    def _ensure_connected(self, timeout=5):
        """确保MQTT客户端已连接"""
        start_time = time.time()
        while not self.connected and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            print("MQTT未连接，尝试重连...")
            self._connect()
            time.sleep(1)  # 给一些时间连接
        
        return self.connected
    
    def _subscribe_topic(self, topic):
        """订阅主题，如果尚未订阅"""
        if topic in self.subscribed_topics:
            return True
        
        if not self._ensure_connected():
            print(f"无法订阅主题 {topic}: MQTT未连接")
            return False
        
        result, mid = self.client.subscribe(topic)
        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"已订阅主题: {topic}")
            self.subscribed_topics.add(topic)
            return True
        else:
            print(f"订阅主题 {topic} 失败")
            return False
    
    def unlock(self, controller_id, sub_lock_number=1):
        """
        解锁指定控制器的指定子锁
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int, optional): 子锁号码，默认为1
            
        Returns:
            bool: 操作是否成功
        """
        topic = f"ULC{controller_id}"
        payload = {"taskId": 1, "payload": {"SLN": sub_lock_number}}
        
        # 同时订阅反馈主题（可选，根据具体需求调整）
        feedback_topic = f"FBK{controller_id}"
        self._subscribe_topic(feedback_topic)
        
        # 发送命令
        return self._send_command(topic, payload)
    
    def query_status(self, controller_id, sub_lock_number=1):
        """
        查询指定控制器的指定子锁状态
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int, optional): 子锁号码，默认为1
            
        Returns:
            bool: 操作是否成功
        """
        topic = f"QRY{controller_id}"
        payload = {"taskId": 2, "payload": {"SLN": sub_lock_number}}
        
        # 同时订阅反馈主题
        feedback_topic = f"FBK{controller_id}"
        self._subscribe_topic(feedback_topic)
        
        # 发送命令
        return self._send_command(topic, payload)
    
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
            # 确保连接已建立
            if not self._ensure_connected():
                print("MQTT未连接，无法发送命令")
                return False
            
            # 将字典转换为JSON字符串
            payload_str = json.dumps(payload)
            
            # 发布消息
            result = self.client.publish(topic, payload_str, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"MQTT命令发送成功: {topic} - {payload_str}")
                return True
            else:
                print(f"MQTT命令发送失败，错误码: {result.rc}")
                return False
                
        except Exception as e:
            print(f"发送MQTT命令时出错: {e}")
            return False
    
    def close(self):
        """
        关闭MQTT连接
        """
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            print("MQTT连接已关闭")
    
    async def async_unlock(self, controller_id, sub_lock_number=1):
        """
        异步解锁指定控制器的指定子锁
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int, optional): 子锁号码，默认为1
            
        Returns:
            bool: 操作是否成功
        """
        return await self._async_send_command(
            lambda: self.unlock(controller_id, sub_lock_number)
        )
    
    async def async_query_status(self, controller_id, sub_lock_number=1):
        """
        异步查询指定控制器的指定子锁状态
        
        Args:
            controller_id (str): 控制器ID
            sub_lock_number (int, optional): 子锁号码，默认为1
            
        Returns:
            bool: 操作是否成功
        """
        return await self._async_send_command(
            lambda: self.query_status(controller_id, sub_lock_number)
        )
    
    async def _async_send_command(self, command_func):
        """
        异步发送MQTT命令
        
        Args:
            command_func: 执行命令的函数
            
        Returns:
            bool: 操作是否成功
        """
        # 将同步方法包装为异步方法
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, command_func)
    
    def __del__(self):
        """
        析构函数，确保关闭连接
        """
        self.close() 