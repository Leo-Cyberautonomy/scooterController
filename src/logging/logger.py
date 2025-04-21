# 日志功能实现 
import logging

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

def log_info(message):
    """记录信息级别的日志。"""
    logging.info(message)

def log_error(message):
    """记录错误级别的日志。"""
    logging.error(message) 