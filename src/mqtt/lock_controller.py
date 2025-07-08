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
        # 使用正确的MQTT服务器配置
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.client = None
        self.connected = False
        self.response_queue = Queue()
        self.subscribed_topics = set()
        
        # 回调函数字典，用于处理特定主题的消息
        self.topic_handlers = {}
        
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
            print(f"开始连接MQTT服务器: {self.mqtt_host}:{self.mqtt_port}, 用户: {self.mqtt_user}")
            self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            # 启动后台线程处理网络流量
            self.client.loop_start()
            print(f"MQTT连接请求已发送，等待连接回调...")
        except Exception as e:
            print(f"MQTT连接异常: {e}")
            import traceback
            traceback.print_exc()
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
            
            # 对data_report主题进行特殊处理
            if topic == "data_report":
                try:
                    data = json.loads(payload)
                    print("=" * 50)
                    print("收到锁控制器响应:")
                    print(f"响应内容: {payload}")
                    
                    # 提取并展示关键信息
                    if isinstance(data, dict):
                        controller_id = data.get("controllerId", "未知")
                        sub_lock = data.get("subLock", "未知")
                        lock_status = data.get("lockStatus", "未知")
                        print(f"控制器ID: {controller_id}")
                        print(f"子锁号: {sub_lock}")
                        print(f"锁状态: {lock_status}")
                    print("=" * 50)
                except json.JSONDecodeError:
                    print(f"无法解析data_report响应JSON: {payload}")
            
            # 如果有特定主题的处理函数，则调用它
            if topic in self.topic_handlers:
                self.topic_handlers[topic](topic, payload)
            
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
        print(f"检查MQTT连接状态: {'已连接' if self.connected else '未连接'}")
        start_time = time.time()
        while not self.connected and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            print("MQTT未连接，尝试重连...")
            self._connect()
            start_time = time.time()
            # 再次等待连接
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.1)
                
            if self.connected:
                print("MQTT重连成功")
            else:
                print("MQTT重连失败")
        
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
        print(f"执行MQTT解锁: 控制器 {controller_id} 的子锁 {sub_lock_number}")
        topic = f"ULC{controller_id}"
        payload = {"taskId": 1, "payload": {"SLN": sub_lock_number}}
        
        # 简化版本的命令发送
        try:
            payload_str = json.dumps(payload)
            self.client.publish(topic, payload_str, qos=1)
            print(f"MQTT开锁命令已发送: {topic} - {payload_str}")
            return True
        except Exception as e:
            print(f"MQTT开锁命令发送失败: {e}")
            return False
    
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
        
        # 确保订阅data_report主题用于接收反馈
        self._subscribe_topic("data_report")
        
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
            # 直接使用client发送命令，不检查连接状态
            # 将字典转换为JSON字符串
            payload_str = json.dumps(payload)
            
            # 发布消息
            result = self.client.publish(topic, payload_str, qos=1)
            print(f"MQTT命令发送: {topic} - {payload_str}")
            return True
                
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
        topic = f"ULC{controller_id}"
        payload = {"taskId": 1, "payload": {"SLN": sub_lock_number}}
        print(f"异步解锁请求: 控制器={controller_id}, 子锁={sub_lock_number}")
        
        # 确保订阅data_report主题
        self._subscribe_topic("data_report")
        
        # 直接发送命令，不使用异步包装
        return self._send_command(topic, payload)
    
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
    
    def subscribe_data_report(self, callback_function=None):
        """
        订阅data_report主题，用于监听锁状态变化
        
        Args:
            callback_function: 收到消息时的回调函数，接收(topic, payload)两个参数
            
        Returns:
            bool: 是否订阅成功
        """
        topic = "data_report"
        success = self._subscribe_topic(topic)
        
        if success and callback_function:
            self.topic_handlers[topic] = callback_function
            
        return success 