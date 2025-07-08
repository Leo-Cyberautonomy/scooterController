import json
import time
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional, Callable, List, Tuple
from logger import get_logger

# 创建日志记录器
logger = get_logger('mqtt_model')

class MQTTModel:
    """MQTT模型类，封装所有MQTT操作功能"""
    
    def __init__(self, host: str = "mqtt.xcubesports.com.cn", 
                 port: int = 1883, 
                 username: str = "myuser", 
                 password: str = "kejin"):
        """
        初始化MQTT模型
        
        Args:
            host: MQTT服务器地址
            port: MQTT服务器端口
            username: MQTT用户名
            password: MQTT密码
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        
        # 客户端状态
        self.client = None
        self.connected = False
        self.subscribed_topics = set()
        
        # 回调函数字典，用于处理特定主题的消息
        self.topic_handlers = {}
        
        # 初始化客户端
        self._init_client()
    
    def _init_client(self):
        """初始化MQTT客户端和连接"""
        # 创建客户端，使用时间戳作为客户端ID
        client_id = f"mqtt_controller_{int(time.time())}"
        self.client = mqtt.Client(client_id=client_id)
        
        # 设置认证信息
        self.client.username_pw_set(self.username, self.password)
        
        # 设置回调函数
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # 启动连接
        self._connect()
    
    def _connect(self):
        """连接到MQTT服务器"""
        try:
            logger.info(f"正在连接MQTT服务器: {self.host}:{self.port}")
            self.client.connect(self.host, self.port, keepalive=60)
            # 启动后台线程处理网络流量
            self.client.loop_start()
        except Exception as e:
            logger.error(f"MQTT连接异常: {e}")
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """连接建立回调函数"""
        if rc == 0:
            logger.info("MQTT连接成功")
            self.connected = True
        else:
            logger.error(f"MQTT连接失败，返回码: {rc}")
            self.connected = False
    
    def _on_message(self, client, userdata, msg):
        """消息接收回调函数"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            logger.debug(f"收到MQTT消息: 主题={topic}, 内容={payload}")
            
            # 如果有特定主题的处理函数，则调用它
            if topic in self.topic_handlers:
                self.topic_handlers[topic](topic, payload)
                
        except Exception as e:
            logger.error(f"处理MQTT消息时出错: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调函数"""
        logger.info(f"MQTT连接断开, 返回码: {rc}")
        self.connected = False
        if rc != 0:
            logger.warning("尝试重新连接...")
            self._connect()
    
    def _ensure_connected(self, timeout: float = 5.0) -> bool:
        """
        确保MQTT客户端已连接
        
        Args:
            timeout: 等待连接的超时时间（秒）
            
        Returns:
            是否已连接
        """
        start_time = time.time()
        while not self.connected and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            logger.warning("MQTT未连接，尝试重连...")
            self._connect()
            start_time = time.time()
            # 再次等待连接
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.1)
                
            if self.connected:
                logger.info("MQTT重连成功")
            else:
                logger.error("MQTT重连失败")
        
        return self.connected
    
    def _subscribe_topic(self, topic: str) -> bool:
        """
        订阅主题，如果尚未订阅
        
        Args:
            topic: 要订阅的主题
            
        Returns:
            是否订阅成功
        """
        if topic in self.subscribed_topics:
            return True
        
        if not self._ensure_connected():
            logger.error(f"无法订阅主题 {topic}: MQTT未连接")
            return False
        
        result, mid = self.client.subscribe(topic)
        if result == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"已订阅主题: {topic}")
            self.subscribed_topics.add(topic)
            return True
        else:
            logger.error(f"订阅主题 {topic} 失败")
            return False
    
    def publish(self, topic: str, payload: Dict[str, Any], qos: int = 1) -> bool:
        """
        发布消息到指定主题
        
        Args:
            topic: 主题
            payload: 消息内容（字典）
            qos: 服务质量等级
            
        Returns:
            是否发布成功
        """
        if not self._ensure_connected():
            logger.error(f"无法发布消息: MQTT未连接")
            return False
        
        try:
            # 使用separators参数移除空格
            payload_str = json.dumps(payload, separators=(',', ':'))
            logger.info(f"发送MQTT命令: 主题={topic}, 内容={payload_str}")
            result = self.client.publish(topic, payload_str, qos=qos)
            logger.info(f"发送MQTT命令: {topic}, {payload_str}")
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"发布消息时出错: {e}")
            return False
    
    def subscribe(self, topic: str, callback: Optional[Callable[[str, str], None]] = None) -> bool:
        """
        订阅主题并设置回调函数
        
        Args:
            topic: 要订阅的主题
            callback: 收到消息时的回调函数，接收(topic, payload)两个参数
            
        Returns:
            是否订阅成功
        """
        success = self._subscribe_topic(topic)
        
        if success and callback:
            self.topic_handlers[topic] = callback
            
        return success
    
    def unsubscribe(self, topic: str) -> bool:
        """
        取消订阅主题
        
        Args:
            topic: 要取消订阅的主题
            
        Returns:
            是否取消订阅成功
        """
        if topic not in self.subscribed_topics:
            return True
        
        if not self._ensure_connected():
            logger.error(f"无法取消订阅主题 {topic}: MQTT未连接")
            return False
        
        result, mid = self.client.unsubscribe(topic)
        if result == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"已取消订阅主题: {topic}")
            self.subscribed_topics.remove(topic)
            if topic in self.topic_handlers:
                del self.topic_handlers[topic]
            return True
        else:
            logger.error(f"取消订阅主题 {topic} 失败")
            return False
    
    def close(self):
        """关闭MQTT连接"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT连接已关闭")
    
    def __del__(self):
        """析构函数，确保资源被正确释放"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.loop_stop()
                self.client.disconnect()
        except:
            pass  # 忽略清理过程中的任何错误
    
    # 锁控制相关方法
    def unlock_lock(self, controller_id: str, sub_lock_number: int = 1) -> bool:
        """
        解锁指定控制器的指定子锁
        
        Args:
            controller_id: 控制器ID
            sub_lock_number: 子锁号码，默认为1
            
        Returns:
            操作是否成功
        """
        topic = f"ULC{controller_id}"
        payload = {"taskId":1,"payload":{"SLN":sub_lock_number}}
        return self.publish(topic, payload)
    
    def query_lock_status(self, controller_id: str, sub_lock_number: int = 1) -> bool:
        """
        查询指定控制器的指定子锁状态
        
        Args:
            controller_id: 控制器ID
            sub_lock_number: 子锁号码，默认为1
            
        Returns:
            操作是否成功
        """
        topic = f"QRY{controller_id}"
        payload = {"taskId":2,"payload":{"SLN":sub_lock_number}}
        
        # 确保订阅data_report主题用于接收反馈
        self._subscribe_topic("data_report")
        
        return self.publish(topic, payload)
    
    def subscribe_lock_status(self, callback: Callable[[str, str], None]) -> bool:
        """
        订阅锁状态变化通知
        
        Args:
            callback: 收到消息时的回调函数，接收(topic, payload)两个参数
            
        Returns:
            是否订阅成功
        """
        return self.subscribe("data_report", callback)
    
    def parse_lock_status(self, payload: str) -> Dict[str, Any]:
        """
        解析锁状态消息
        
        Args:
            payload: 消息内容（JSON字符串）
            
        Returns:
            解析后的锁状态信息
        """
        try:
            data = json.loads(payload)
            return {
                "controller_id": data.get("controllerId", "未知"),
                "sub_lock": data.get("subLock", "未知"),
                "lock_status": data.get("lockStatus", "未知"),
                "battery_level": data.get("batteryLevel", 0),
                "signal_strength": data.get("signalStrength", 0),
                "open_type": data.get("openType", -1),
                "timestamp": data.get("timestamp", "")
            }
        except json.JSONDecodeError:
            logger.error(f"无法解析锁状态消息: {payload}")
            return {}

# 测试代码
if __name__ == "__main__":
    logger.info("开始测试MQTT模型...")
    
    # 创建MQTT模型实例
    mqtt_model = MQTTModel()
    
    # 等待连接建立
    time.sleep(2)
    
    # 测试订阅锁状态
    def on_lock_status(topic, payload):
        logger.info(f"收到锁状态更新: {topic}")
        status = mqtt_model.parse_lock_status(payload)
        logger.info(f"锁状态详情: {status}")
    
    mqtt_model.subscribe_lock_status(on_lock_status)
    
    # 获取控制器ID
    controller_id = "866846061051685"  # 使用配置文件中的第一个控制器ID
    
    
    # 测试解锁
    logger.info(f"尝试解锁控制器 {controller_id}...")
    mqtt_model.unlock_lock(controller_id,1)
    
    # 等待一段时间以接收响应
    time.sleep(5)
    
    # 关闭连接
    logger.info("测试完成，关闭连接...")
    mqtt_model.close() 