"""
数据模型定义，用于管理车辆和锁的对应关系
"""
import sqlite3
import os
import json
from datetime import datetime

class Database:
    """数据库管理类，负责与SQLite数据库的交互"""
    
    def __init__(self, db_path='scooter_manager.db'):
        """初始化数据库连接"""
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self.connect()
        self.create_tables()
        
        # 检查是否需要从配置文件导入初始数据
        if os.path.exists('config/devices.json') and self.is_database_empty():
            self.import_from_config()
    
    def connect(self):
        """连接到数据库"""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
        self.cursor = self.connection.cursor()
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
    
    def commit(self):
        """提交事务"""
        if self.connection:
            self.connection.commit()
    
    def create_tables(self):
        """创建必要的数据表"""
        # 创建车辆表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS scooters (
            scooter_id TEXT PRIMARY KEY,
            scooter_name TEXT,
            bluetooth_address TEXT UNIQUE,
            lock_controller_id TEXT,
            sub_lock_number INTEGER,
            status TEXT DEFAULT '空闲',
            last_operation_time TEXT
        )
        ''')
        
        # 创建锁控制器表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS lock_controllers (
            controller_id TEXT PRIMARY KEY,
            controller_name TEXT,
            mqtt_topic_prefix TEXT UNIQUE,
            status TEXT DEFAULT '正常'
        )
        ''')
        
        # 创建操作记录表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS operation_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scooter_id TEXT,
            controller_id TEXT,
            sub_lock_number INTEGER,
            operation_type TEXT,
            operation_time TEXT,
            status TEXT,
            FOREIGN KEY (scooter_id) REFERENCES scooters(scooter_id),
            FOREIGN KEY (controller_id) REFERENCES lock_controllers(controller_id)
        )
        ''')
        
        self.commit()

    def is_database_empty(self):
        """检查数据库是否为空"""
        self.cursor.execute("SELECT COUNT(*) FROM scooters")
        scooter_count = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM lock_controllers")
        lock_count = self.cursor.fetchone()[0]
        
        return scooter_count == 0 and lock_count == 0
    
    def import_from_config(self):
        """从配置文件导入数据"""
        try:
            with open('config/devices.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # 导入锁控制器
            for controller in config.get('lock_controllers', []):
                self.cursor.execute('''
                INSERT INTO lock_controllers (controller_id, controller_name, mqtt_topic_prefix, status)
                VALUES (?, ?, ?, ?)
                ''', (
                    controller['controller_id'],
                    controller['controller_name'],
                    controller['mqtt_topic_prefix'],
                    controller['status']
                ))
            
            # 导入车辆信息
            for scooter in config.get('scooters', []):
                # 根据锁编号获取正确的控制器ID和子锁号
                lock_number = scooter.get('lock_number')
                controller_id = None
                sub_lock_number = None
                
                if lock_number and 1 <= lock_number <= 10:
                    if 1 <= lock_number <= 5:
                        controller_id = "866846061120977"
                        sub_lock_number = lock_number
                    elif 6 <= lock_number <= 10:
                        controller_id = "866846061051685"
                        sub_lock_number = lock_number - 5
                
                self.cursor.execute('''
                INSERT INTO scooters (scooter_id, scooter_name, bluetooth_address, lock_controller_id, sub_lock_number, status, last_operation_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    scooter['scooter_id'],
                    scooter['scooter_name'],
                    scooter['bluetooth_address'],
                    controller_id,
                    sub_lock_number,
                    scooter['status'],
                    datetime.now().isoformat()
                ))
            
            self.commit()
            print("成功从配置文件导入数据")
            
        except Exception as e:
            print(f"从配置文件导入数据时出错: {e}")
            # 回滚事务
            if self.connection:
                self.connection.rollback()

class ScooterManager:
    """车辆管理类，提供添加、查询、更新车辆信息的功能"""
    
    def __init__(self, database):
        """初始化车辆管理器"""
        self.db = database
    
    def add_scooter(self, scooter_id, scooter_name, bluetooth_address, lock_controller_id=None, sub_lock_number=None):
        """添加新车辆"""
        try:
            self.db.cursor.execute('''
            INSERT INTO scooters (scooter_id, scooter_name, bluetooth_address, lock_controller_id, sub_lock_number, last_operation_time)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (scooter_id, scooter_name, bluetooth_address, lock_controller_id, sub_lock_number, datetime.now().isoformat()))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_scooter(self, scooter_id=None, bluetooth_address=None):
        """通过ID或蓝牙地址查询车辆"""
        if scooter_id:
            self.db.cursor.execute('SELECT * FROM scooters WHERE scooter_id = ?', (scooter_id,))
        elif bluetooth_address:
            self.db.cursor.execute('SELECT * FROM scooters WHERE bluetooth_address = ?', (bluetooth_address,))
        else:
            return None
        
        result = self.db.cursor.fetchone()
        return dict(result) if result else None
    
    def get_all_scooters(self):
        """获取所有车辆"""
        self.db.cursor.execute('SELECT * FROM scooters')
        return [dict(row) for row in self.db.cursor.fetchall()]
    
    def update_scooter_lock(self, scooter_id, lock_controller_id, sub_lock_number):
        """更新车辆关联的锁信息"""
        try:
            self.db.cursor.execute('''
            UPDATE scooters 
            SET lock_controller_id = ?, sub_lock_number = ?, last_operation_time = ?
            WHERE scooter_id = ?
            ''', (lock_controller_id, sub_lock_number, datetime.now().isoformat(), scooter_id))
            self.db.commit()
            return True
        except Exception as e:
            print(f"更新车辆锁信息出错: {e}")
            return False
    
    def update_scooter_status(self, scooter_id, status):
        """更新车辆状态"""
        try:
            self.db.cursor.execute('''
            UPDATE scooters 
            SET status = ?, last_operation_time = ?
            WHERE scooter_id = ?
            ''', (status, datetime.now().isoformat(), scooter_id))
            self.db.commit()
            return True
        except Exception as e:
            print(f"更新车辆状态出错: {e}")
            return False

class LockManager:
    """锁管理类，提供添加、查询、更新锁信息的功能"""
    
    def __init__(self, database):
        """初始化锁管理器"""
        self.db = database
    
    def add_lock_controller(self, controller_id, controller_name, mqtt_topic_prefix):
        """添加新的锁控制器"""
        try:
            self.db.cursor.execute('''
            INSERT INTO lock_controllers (controller_id, controller_name, mqtt_topic_prefix)
            VALUES (?, ?, ?)
            ''', (controller_id, controller_name, mqtt_topic_prefix))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_lock_controller(self, controller_id):
        """通过ID查询锁控制器"""
        self.db.cursor.execute('SELECT * FROM lock_controllers WHERE controller_id = ?', (controller_id,))
        result = self.db.cursor.fetchone()
        return dict(result) if result else None
    
    def get_all_lock_controllers(self):
        """获取所有锁控制器"""
        self.db.cursor.execute('SELECT * FROM lock_controllers')
        return [dict(row) for row in self.db.cursor.fetchall()]
    
    def log_operation(self, scooter_id, controller_id, sub_lock_number, operation_type, status):
        """记录操作日志"""
        try:
            self.db.cursor.execute('''
            INSERT INTO operation_logs (scooter_id, controller_id, sub_lock_number, operation_type, operation_time, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (scooter_id, controller_id, sub_lock_number, operation_type, datetime.now().isoformat(), status))
            self.db.commit()
            return True
        except Exception as e:
            print(f"记录操作日志出错: {e}")
            return False 