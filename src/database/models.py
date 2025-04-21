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