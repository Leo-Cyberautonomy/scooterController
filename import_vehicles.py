#!/usr/bin/env python3
"""
车辆和锁信息批量导入脚本
包含标记机制确保只运行一次
"""
import os
import sys
import sqlite3
from datetime import datetime

# 确保当前目录在项目根目录中
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.controller.scooter_controller import ScooterController

# 导入标记文件路径
IMPORT_FLAG_FILE = ".import_completed"

def is_already_imported():
    """检查是否已经完成导入"""
    # 检查标记文件是否存在
    if os.path.exists(IMPORT_FLAG_FILE):
        with open(IMPORT_FLAG_FILE, "r") as flag_file:
            timestamp = flag_file.read().strip()
            print(f"数据已经在 {timestamp} 导入过。")
            return True
    
    # 另一种检查方法：通过数据库中的记录数判断
    try:
        controller = ScooterController()
        scooters = controller.scooter_manager.get_all_scooters()
        locks = controller.lock_manager.get_all_lock_controllers()
        
        if len(scooters) >= 10 and len(locks) >= 10:
            print(f"数据库中已存在足够数量的车辆({len(scooters)})和锁控制器({len(locks)})记录。")
            # 创建标记文件以避免将来再次检查
            create_import_flag()
            return True
    except Exception as e:
        print(f"检查数据库记录时出错: {e}")
    
    return False

def create_import_flag():
    """创建导入完成标记文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(IMPORT_FLAG_FILE, "w") as flag_file:
        flag_file.write(timestamp)
    print(f"已创建导入标记，时间戳: {timestamp}")

def main():
    """导入车辆和锁信息"""
    print("开始车辆和锁信息导入过程...")
    
    # 检查是否已经导入过
    if is_already_imported():
        user_input = input("数据似乎已经导入过。是否强制重新导入？(y/N): ").strip().lower()
        if user_input != 'y':
            print("导入操作已取消。")
            return
        else:
            print("将强制重新导入数据...")
    
    # 创建控制器
    controller = ScooterController()
    
    # 车辆信息列表 (QR code作为id，Mac作为蓝牙地址)
    vehicles = [
        {"id": "OKCB24070205112", "mac": "78:05:41:3F:E9:29", "imei": "867689061117695", "name": "电动车#1"},
        {"id": "OKCB2405080470", "mac": "78:05:41:3F:EA:E7", "imei": "867689061222206", "name": "电动车#2"},
        {"id": "OKCB24070205126", "mac": "78:05:41:3F:E9:77", "imei": "867689061400752", "name": "电动车#3"},
        {"id": "OKCB24070205125", "mac": "78:05:41:3F:EA:20", "imei": "867689061118545", "name": "电动车#4"},
        {"id": "OKCB24050804138", "mac": "78:05:41:3F:E9:6A", "imei": "867689061134732", "name": "电动车#5"},
        {"id": "OKCB2407020583", "mac": "78:05:41:3F:E9:D7", "imei": "867689061128874", "name": "电动车#6"},
        {"id": "OKCB2407020568", "mac": "78:05:41:3F:E9:6F", "imei": "867689061400562", "name": "电动车#7"},
        {"id": "OKCB2407020525", "mac": "78:05:41:3F:EA:E2", "imei": "867689061333631", "name": "电动车#8"},
        {"id": "OKCB2407020597", "mac": "78:05:41:3F:EB:0F", "imei": "867689061215606", "name": "电动车#9"},
        {"id": "OKCB24070205111", "mac": "78:05:41:3F:EA:23", "imei": "867689061128148", "name": "电动车#10"}
    ]
    
    # 锁控制器信息 (根据题目，添加10个锁，暂用主控1和主控2的锁控制器ID作为示例)
    locks = [
        {"id": "866846061120977", "name": "车锁#1", "mqtt_prefix": "ULC866846061120977"},
        {"id": "866846061051685", "name": "车锁#2", "mqtt_prefix": "ULC866846061051685"},
        {"id": "866846061120978", "name": "车锁#3", "mqtt_prefix": "ULC866846061120978"},
        {"id": "866846061120979", "name": "车锁#4", "mqtt_prefix": "ULC866846061120979"},
        {"id": "866846061120980", "name": "车锁#5", "mqtt_prefix": "ULC866846061120980"},
        {"id": "866846061120981", "name": "车锁#6", "mqtt_prefix": "ULC866846061120981"},
        {"id": "866846061120982", "name": "车锁#7", "mqtt_prefix": "ULC866846061120982"},
        {"id": "866846061120983", "name": "车锁#8", "mqtt_prefix": "ULC866846061120983"},
        {"id": "866846061120984", "name": "车锁#9", "mqtt_prefix": "ULC866846061120984"},
        {"id": "866846061120985", "name": "车锁#10", "mqtt_prefix": "ULC866846061120985"}
    ]
    
    # 成功导入计数
    successful_locks = 0
    successful_scooters = 0
    successful_associations = 0
    
    # 导入锁控制器
    print("\n正在导入锁控制器信息...")
    for lock in locks:
        try:
            success = controller.register_lock_controller(
                lock["id"], 
                lock["name"], 
                lock["mqtt_prefix"]
            )
            status = "成功" if success else "失败(可能已存在)"
            print(f"导入锁 {lock['name']} ({lock['id']}): {status}")
            if success:
                successful_locks += 1
        except Exception as e:
            print(f"导入锁 {lock['name']} 时出错: {e}")
    
    # 导入车辆并关联锁
    print("\n正在导入车辆信息...")
    for i, vehicle in enumerate(vehicles):
        try:
            # 锁的索引从0开始，子锁号从1开始
            lock_index = i
            sub_lock_number = 1
            
            # 首先注册车辆
            success = controller.register_scooter(
                vehicle["id"],
                vehicle["name"],
                vehicle["mac"]
            )
            
            status = "成功" if success else "失败(可能已存在)"
            print(f"导入车辆 {vehicle['name']} ({vehicle['id']}): {status}")
            if success:
                successful_scooters += 1
            
            # 然后关联锁
            if lock_index < len(locks):
                # 无论车辆是否新建，都尝试更新关联关系
                lock_success = controller.update_scooter_lock_association(
                    vehicle["id"], 
                    locks[lock_index]["id"], 
                    sub_lock_number
                )
                lock_status = "成功" if lock_success else "失败"
                print(f"  关联到锁 {locks[lock_index]['name']} (子锁 {sub_lock_number}): {lock_status}")
                if lock_success:
                    successful_associations += 1
        except Exception as e:
            print(f"导入车辆 {vehicle['name']} 时出错: {e}")
    
    print("\n导入摘要:")
    print(f"- 成功导入锁控制器: {successful_locks}/{len(locks)}")
    print(f"- 成功导入车辆: {successful_scooters}/{len(vehicles)}")
    print(f"- 成功建立关联: {successful_associations}/{len(vehicles)}")
    
    print("\n数据导入完成!")
    print("您可以通过运行主程序 'python main.py' 并进入车辆管理和锁管理界面查看导入的数据。")
    
    # 创建标记文件，标记导入已完成
    create_import_flag()

if __name__ == "__main__":
    main() 