# 主界面 —— 电动车控制程序
import sys
import os
import asyncio
import threading
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
from datetime import datetime

# 将项目根目录添加到Python搜索路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.bluetooth.ble_communication import discover_devices, connect_to_device, send_command
from src.bluetooth.command_handler import format_command, parse_response
from src.controller.scooter_controller import ScooterController

class MainWindow:
    def __init__(self, root):
        """初始化主窗口"""
        self.root = root
        self.root.title("智能滑板车管理系统")
        self.root.geometry("1200x700")
        
        # 初始化控制器
        self.scooter_controller = ScooterController()
        
        # 设置变量
        self.device_var = tk.StringVar()
        self.password_var = tk.StringVar(value="zk301")  # 默认密码zk301
        self.operation_var = tk.StringVar()
        
        # 存储操作指令选择变量
        self.operations = [
            "ECU锁：解锁",       # AT+BKSCT=<BLE密码>,0
            "ECU锁：上锁",       # AT+BKSCT=<BLE密码>,1
            "ECU锁：增强解锁",   # AT+BKSCT=<BLE密码>,2
            "电池锁：解锁",      # AT+BKSCT=<BLE密码>,10
            "电池锁：上锁",      # AT+BKSCT=<BLE密码>,11
            "车桩锁：解锁",      # AT+BKSCT=<BLE密码>,20
            "车桩锁：上锁",      # AT+BKSCT=<BLE密码>,21
            "篮子锁：解锁",      # AT+BKSCT=<BLE密码>,30
            "篮子锁：上锁",      # AT+BKSCT=<BLE密码>,31
            "备份锁：解锁",      # AT+BKSCT=<BLE密码>,40
            "备份锁：上锁",      # AT+BKSCT=<BLE密码>,41
            "打开头灯",         # AT+BKLED=<BLE密码>,0,1
            "关闭头灯",         # AT+BKLED=<BLE密码>,0,0
            "查询设备信息",     # AT+BKINF=<BLE密码>,0
            "固件版本查询",     # AT+BKVER=<BLE密码>,0
            "修改密码"          # AT+BKPWD=<BLE密码>,<新密码>
        ]
        # 默认选择第一个操作
        self.operation_var.set(self.operations[0])
        
        # 创建UI
        self.create_frames()
        
        # 创建自动更新记录查看按钮
        self.add_auto_update_history_button()
        
        # 用于保存当前已连接的设备客户端对象
        self.connected_client = None
        
        # 设备列表
        self.device_list = []

    def create_frames(self):
        """创建整个界面，包括顶部导航及功能区"""
        # -------------------------
        # 顶部导航栏（或侧边栏均可，这里采用顶部导航栏）
        self.nav_frame = tk.Frame(self.root, bg='lightblue')
        self.nav_frame.pack(side=tk.TOP, fill=tk.X)

        self.device_button = tk.Button(self.nav_frame, text="设备管理", command=self.show_device_management)
        self.device_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.operation_button = tk.Button(self.nav_frame, text="操作指令", command=self.show_operation_commands)
        self.operation_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.feedback_button = tk.Button(self.nav_frame, text="反馈日志", command=self.show_feedback)
        self.feedback_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 新增车辆管理和锁管理按钮
        self.scooter_mgmt_button = tk.Button(self.nav_frame, text="车辆管理", command=self.show_scooter_management)
        self.scooter_mgmt_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.lock_mgmt_button = tk.Button(self.nav_frame, text="锁管理", command=self.show_lock_management)
        self.lock_mgmt_button.pack(side=tk.LEFT, padx=5, pady=5)

        # -------------------------
        # 设备管理区
        self.device_frame = tk.Frame(self.root)
        self.device_frame.pack(fill=tk.BOTH, expand=True)

        # 扫描设备按钮
        self.scan_button = tk.Button(self.device_frame, text="扫描设备", command=self.start_scan_thread)
        self.scan_button.pack(pady=10)

        # 下拉设备列表
        self.device_menu = tk.OptionMenu(self.device_frame, self.device_var, ())
        self.device_menu.pack(pady=10)

        # 设备连接状态
        self.connection_status = tk.Label(self.device_frame, text="连接状态: 未连接", fg="red")
        self.connection_status.pack(pady=10)

        # 新增连接设备按钮
        self.connect_button = tk.Button(self.device_frame, text="连接设备", command=self.connect_device)
        self.connect_button.pack(pady=10)

        # -------------------------
        # 操作指令区（命令中心）
        self.operation_frame = tk.Frame(self.root)
        # 操作指令区内先显示操作下拉菜单及"执行"按钮
        self.operation_label = tk.Label(self.operation_frame, text="请选择操作：")
        self.operation_label.pack(pady=10)
        self.operation_menu = tk.OptionMenu(self.operation_frame, self.operation_var, *self.operations, command=self.operation_changed)
        self.operation_menu.pack(pady=10)

        # 修改密码时需要额外输入新密码
        self.new_password_frame = tk.Frame(self.operation_frame)
        self.new_password_label = tk.Label(self.new_password_frame, text="请输入新密码：")
        self.new_password_entry = tk.Entry(self.new_password_frame, show="*")
        # 默认隐藏新密码相关UI
        self.new_password_frame.pack_forget()

        # 执行按钮
        self.execute_button = tk.Button(self.operation_frame, text="执行", command=self.execute_command)
        self.execute_button.pack(pady=10)

        # -------------------------
        # 反馈日志区（状态监控）
        self.feedback_frame = tk.Frame(self.root)
        self.log_output = tk.Text(self.feedback_frame, height=15, width=70)
        self.log_output.pack(pady=10)
        self.status_info = tk.Label(self.feedback_frame, text="设备信息: 无")
        self.status_info.pack(pady=5)
        
        # -------------------------
        # 车辆管理区（新增）
        self.scooter_mgmt_frame = tk.Frame(self.root)
        
        # 创建车辆列表
        self.scooter_tree_frame = tk.Frame(self.scooter_mgmt_frame)
        self.scooter_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.scooter_tree = ttk.Treeview(self.scooter_tree_frame, columns=("ID", "名称", "蓝牙地址", "锁控制器", "子锁号", "状态"))
        self.scooter_tree.heading("#0", text="")
        self.scooter_tree.heading("ID", text="车辆ID")
        self.scooter_tree.heading("名称", text="车辆名称")
        self.scooter_tree.heading("蓝牙地址", text="蓝牙地址")
        self.scooter_tree.heading("锁控制器", text="锁控制器")
        self.scooter_tree.heading("子锁号", text="子锁号")
        self.scooter_tree.heading("状态", text="状态")
        
        self.scooter_tree.column("#0", width=0, stretch=tk.NO)
        self.scooter_tree.column("ID", width=100)
        self.scooter_tree.column("名称", width=100)
        self.scooter_tree.column("蓝牙地址", width=150)
        self.scooter_tree.column("锁控制器", width=100)
        self.scooter_tree.column("子锁号", width=50)
        self.scooter_tree.column("状态", width=80)
        
        self.scooter_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scooter_scrollbar = ttk.Scrollbar(self.scooter_tree_frame, orient=tk.VERTICAL, command=self.scooter_tree.yview)
        self.scooter_tree.configure(yscrollcommand=scooter_scrollbar.set)
        scooter_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 车辆管理按钮区
        self.scooter_btn_frame = tk.Frame(self.scooter_mgmt_frame)
        self.scooter_btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.refresh_scooter_btn = tk.Button(self.scooter_btn_frame, text="刷新列表", command=self.refresh_scooter_list)
        self.refresh_scooter_btn.pack(side=tk.LEFT, padx=5)
        
        self.add_scooter_btn = tk.Button(self.scooter_btn_frame, text="添加车辆", command=self.add_scooter)
        self.add_scooter_btn.pack(side=tk.LEFT, padx=5)
        
        # -------------------------
        # 锁管理区（新增）
        self.lock_mgmt_frame = tk.Frame(self.root)
        
        # 创建锁控制器列表
        self.lock_tree_frame = tk.Frame(self.lock_mgmt_frame)
        self.lock_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.lock_tree = ttk.Treeview(self.lock_tree_frame, columns=("ID", "名称", "MQTT主题前缀", "状态"))
        self.lock_tree.heading("#0", text="")
        self.lock_tree.heading("ID", text="控制器ID")
        self.lock_tree.heading("名称", text="控制器名称")
        self.lock_tree.heading("MQTT主题前缀", text="MQTT主题前缀")
        self.lock_tree.heading("状态", text="状态")
        
        self.lock_tree.column("#0", width=0, stretch=tk.NO)
        self.lock_tree.column("ID", width=100)
        self.lock_tree.column("名称", width=100)
        self.lock_tree.column("MQTT主题前缀", width=200)
        self.lock_tree.column("状态", width=80)
        
        self.lock_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        lock_scrollbar = ttk.Scrollbar(self.lock_tree_frame, orient=tk.VERTICAL, command=self.lock_tree.yview)
        self.lock_tree.configure(yscrollcommand=lock_scrollbar.set)
        lock_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 锁管理按钮区
        self.lock_btn_frame = tk.Frame(self.lock_mgmt_frame)
        self.lock_btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.refresh_lock_btn = tk.Button(self.lock_btn_frame, text="刷新列表", command=self.refresh_lock_list)
        self.refresh_lock_btn.pack(side=tk.LEFT, padx=5)
        
        self.add_lock_btn = tk.Button(self.lock_btn_frame, text="添加锁控制器", command=self.add_lock_controller)
        self.add_lock_btn.pack(side=tk.LEFT, padx=5)
        
        self.test_unlock_btn = tk.Button(self.lock_btn_frame, text="测试解锁", command=self.test_unlock)
        self.test_unlock_btn.pack(side=tk.LEFT, padx=5)

        # -------------------------
        # 自动更新历史记录区
        self.auto_update_frame = tk.Frame(self.root)
        self.auto_update_button = tk.Button(self.auto_update_frame, text="查看自动更新记录", command=self.show_auto_update_history)
        self.auto_update_button.pack(pady=5)

        # 默认显示设备管理区
        self.show_device_management()

    def show_device_management(self):
        """显示设备管理界面，同时隐藏其它功能区。"""
        self.device_frame.pack(fill=tk.BOTH, expand=True)
        self.operation_frame.pack_forget()
        self.feedback_frame.pack_forget()
        self.scooter_mgmt_frame.pack_forget()
        self.lock_mgmt_frame.pack_forget()

    def show_operation_commands(self):
        """显示操作指令界面，同时隐藏其它功能区。"""
        self.device_frame.pack_forget()
        self.operation_frame.pack(fill=tk.BOTH, expand=True)
        self.feedback_frame.pack_forget()
        self.scooter_mgmt_frame.pack_forget()
        self.lock_mgmt_frame.pack_forget()

    def show_feedback(self):
        """显示反馈日志界面，同时隐藏其它功能区。"""
        self.device_frame.pack_forget()
        self.operation_frame.pack_forget()
        self.feedback_frame.pack(fill=tk.BOTH, expand=True)
        self.scooter_mgmt_frame.pack_forget()
        self.lock_mgmt_frame.pack_forget()
    
    def show_scooter_management(self):
        """显示车辆管理界面，同时隐藏其它功能区。"""
        self.device_frame.pack_forget()
        self.operation_frame.pack_forget()
        self.feedback_frame.pack_forget()
        self.scooter_mgmt_frame.pack(fill=tk.BOTH, expand=True)
        self.lock_mgmt_frame.pack_forget()
        # 刷新车辆列表
        self.refresh_scooter_list()
    
    def show_lock_management(self):
        """显示锁管理界面，同时隐藏其它功能区。"""
        self.device_frame.pack_forget()
        self.operation_frame.pack_forget()
        self.feedback_frame.pack_forget()
        self.scooter_mgmt_frame.pack_forget()
        self.lock_mgmt_frame.pack(fill=tk.BOTH, expand=True)
        # 刷新锁列表
        self.refresh_lock_list()
        
    def start_scan_thread(self):
        """启动一个新线程扫描附近蓝牙设备，避免阻塞Tkinter主线程。"""
        scan_thread = threading.Thread(target=self.scan_devices)
        scan_thread.start()

    def scan_devices(self):
        """异步扫描附近的蓝牙设备，并更新设备列表（在新线程中运行）。"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.device_list = loop.run_until_complete(discover_devices())
        loop.close()
        # 更新设备列表需在主线程中进行
        self.root.after(0, self.update_device_menu)

    def update_device_menu(self):
        """更新设备选择下拉菜单，若设备无名称则显示MAC地址。"""
        device_names = [self.get_display_name(device) for device in self.device_list]
        self.device_var.set(device_names[0] if device_names else "无设备")
        self.device_menu['menu'].delete(0, 'end')
        for name in device_names:
            self.device_menu['menu'].add_command(label=name, command=tk._setit(self.device_var, name))

    def get_display_name(self, device):
        """返回设备的显示名称，如果设备名称为空，则返回设备地址"""
        return device.name if (device.name and device.name.strip() != "") else device.address

    def operation_changed(self, value):
        """当用户选择操作变化时，如果选择 '修改密码' 显示新密码输入框，否则隐藏。"""
        if value == "修改密码":
            self.new_password_frame.pack(pady=5)
            self.new_password_label.pack(side=tk.LEFT)
            self.new_password_entry.pack(side=tk.LEFT)
        else:
            self.new_password_frame.pack_forget()

    def execute_command(self):
        """根据用户选择的操作组合AT命令并发送，然后在反馈区域显示返回信息。"""
        # 检查设备是否选择
        selected_device = next((device for device in self.device_list if self.get_display_name(device) == self.device_var.get()), None)
        if not selected_device:
            messagebox.showerror("错误", "请选择一个设备")
            return
            
        # 使用默认BLE密码
        ble_pwd = self.password_var.get().strip()

        # 根据操作构造命令
        operation = self.operation_var.get()
        
        # 对于解锁操作，使用联动解锁功能
        if operation == "ECU锁：解锁":
            self.log_output.insert(tk.END, f"操作: {operation}\n同步解锁车辆ECU和物理锁...\n")
            self.log_output.see(tk.END)
            
            # 查找设备对应的车辆ID
            scooter_id = None
            for scooter in self.scooter_controller.scooter_manager.get_all_scooters():
                if scooter["bluetooth_address"] == selected_device.address:
                    scooter_id = scooter["scooter_id"]
                    break
            
            if not scooter_id:
                self.log_output.insert(tk.END, "错误: 找不到对应的车辆，请先在车辆管理中注册设备\n")
                self.log_output.see(tk.END)
                return
                
            # 启动解锁任务
            def unlock_task():
                try:
                    ble_success, mqtt_success = asyncio.run(
                        self.scooter_controller.unlock_scooter(scooter_id, ble_pwd)
                    )
                    
                    # 在主线程中更新UI
                    self.root.after(0, lambda: self._update_unlock_result(ble_success, mqtt_success, scooter_id))
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: self.log_output.insert(tk.END, f"解锁操作异常: {error_msg}\n"))
                    self.root.after(0, lambda: self.log_output.see(tk.END))
            
            # 在新线程中执行解锁
            threading.Thread(target=unlock_task).start()
            return
            
        # 定义锁命令映射：键为操作名称，值为对应的 <Lock Command> 参数
        lock_commands = {
            "ECU锁：上锁": "1",
            "ECU锁：增强解锁": "2",
            "电池锁：解锁": "10",
            "电池锁：上锁": "11",
            "车桩锁：解锁": "20",
            "车桩锁：上锁": "21",
            "篮子锁：解锁": "30",
            "篮子锁：上锁": "31",
            "备份锁：解锁": "40",
            "备份锁：上锁": "41"
        }
        if operation in lock_commands:
            command = f"AT+BKSCT={ble_pwd},{lock_commands[operation]}"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
        elif operation == "打开头灯":
            command = f"AT+BKLED={ble_pwd},0,1"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
        elif operation == "关闭头灯":
            command = f"AT+BKLED={ble_pwd},0,0"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
        elif operation == "查询设备信息":
            command = f"AT+BKINF={ble_pwd},0"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
        elif operation == "固件版本查询":
            command = f"AT+BKVER={ble_pwd},0"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
        elif operation == "修改密码":
            new_pwd = self.new_password_entry.get().strip()
            if not new_pwd:
                messagebox.showerror("错误", "请输入新密码")
                return
            command = f"AT+BKPWD={ble_pwd},{new_pwd}"
            char_uuid = "00002c10-0000-1000-8000-00805f9b34fb"
        else:
            messagebox.showerror("错误", "未知操作")
            return

        # 记录操作、发送命令及使用的UUID到反馈区
        self.log_output.insert(tk.END, f"操作: {operation}\n发送命令: {command}\n发送至 UUID: {char_uuid}\n")
        self.log_output.see(tk.END)
        # 使用已建立的连接发送命令，如果当前没有有效的连接则尝试重新连接
        try:
            if self.connected_client is None or not self.connected_client.is_connected:
                self.log_output.insert(tk.END, "当前未连接设备，正在尝试重新连接...\n")
                self.log_output.see(tk.END)
                self.connected_client = asyncio.run(connect_to_device(selected_device.address))

            if self.connected_client and self.connected_client.is_connected:
                response = asyncio.run(send_command(self.connected_client, command, char_uuid))
                parsed_response = parse_response(response) if response else "无响应"
                self.log_output.insert(tk.END, f"响应: {parsed_response}\n")
                self.log_output.see(tk.END)
                self.status_info.config(text=f"设备信息: {parsed_response}")
            else:
                self.log_output.insert(tk.END, "无法连接设备\n")
                self.log_output.see(tk.END)
        except Exception as e:
            error_msg = str(e)
            self.log_output.insert(tk.END, f"命令执行异常: {error_msg}\n")
            self.log_output.see(tk.END)
            
    def _update_unlock_result(self, ble_success, mqtt_success, scooter_id):
        """更新解锁结果到界面"""
        if ble_success and mqtt_success:
            self.log_output.insert(tk.END, f"车辆 {scooter_id} 解锁成功：ECU解锁 ✓ 物理锁解锁 ✓\n")
            self.status_info.config(text=f"设备信息: 车辆和物理锁均已解锁")
        elif ble_success:
            self.log_output.insert(tk.END, f"车辆 {scooter_id} 部分解锁：ECU解锁 ✓ 物理锁解锁 ✗\n")
            self.status_info.config(text=f"设备信息: 车辆已解锁，但物理锁解锁失败")
        elif mqtt_success:
            self.log_output.insert(tk.END, f"车辆 {scooter_id} 部分解锁：ECU解锁 ✗ 物理锁解锁 ✓\n")
            self.status_info.config(text=f"设备信息: 物理锁已解锁，但车辆ECU解锁失败")
        else:
            self.log_output.insert(tk.END, f"车辆 {scooter_id} 解锁失败：ECU解锁 ✗ 物理锁解锁 ✗\n")
            self.status_info.config(text=f"设备信息: 解锁失败，请检查连接和密码")
        
        self.log_output.see(tk.END)

    def connect_device(self):
        """尝试与选中的蓝牙设备建立连接，并更新连接状态，同时保存连接对象。"""
        selected_device = next((device for device in self.device_list if self.get_display_name(device) == self.device_var.get()), None)
        if not selected_device:
            messagebox.showerror("错误", "请选择一个设备")
            return

        def connect_thread():
            try:
                # 使用 asyncio.run 在新线程中进行连接操作
                client = asyncio.run(connect_to_device(selected_device.address))
                if client and client.is_connected:
                    self.connected_client = client  # 保存连接对象
                    self.root.after(0, lambda: self.connection_status.config(text="连接状态: 连接成功", fg="green"))
                else:
                    self.connected_client = None
                    self.root.after(0, lambda: self.connection_status.config(text="连接状态: 连接失败", fg="red"))
            except Exception as e:
                self.connected_client = None
                error_msg = str(e)
                self.root.after(0, lambda: self.connection_status.config(text=f"连接状态: 异常 {error_msg}", fg="red"))

        threading.Thread(target=connect_thread).start()

    # 新增方法：车辆管理相关
    def refresh_scooter_list(self):
        """刷新车辆列表"""
        # 清空现有数据
        for item in self.scooter_tree.get_children():
            self.scooter_tree.delete(item)
        
        # 获取所有车辆
        scooters = self.scooter_controller.scooter_manager.get_all_scooters()
        
        # 添加到列表
        for scooter in scooters:
            self.scooter_tree.insert("", tk.END, values=(
                scooter["scooter_id"],
                scooter["scooter_name"],
                scooter["bluetooth_address"],
                scooter["lock_controller_id"] or "无",
                scooter["sub_lock_number"] or "无",
                scooter["status"]
            ))
    
    def add_scooter(self):
        """添加新车辆"""
        # 弹出窗口获取信息
        add_window = tk.Toplevel(self.root)
        add_window.title("添加新车辆")
        add_window.geometry("400x300")
        
        # 车辆ID
        tk.Label(add_window, text="车辆ID:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        scooter_id_var = tk.StringVar()
        tk.Entry(add_window, textvariable=scooter_id_var, width=30).grid(row=0, column=1, padx=10, pady=10)
        
        # 车辆名称
        tk.Label(add_window, text="车辆名称:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        scooter_name_var = tk.StringVar()
        tk.Entry(add_window, textvariable=scooter_name_var, width=30).grid(row=1, column=1, padx=10, pady=10)
        
        # 蓝牙地址
        tk.Label(add_window, text="蓝牙地址:").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
        bluetooth_address_var = tk.StringVar()
        tk.Entry(add_window, textvariable=bluetooth_address_var, width=30).grid(row=2, column=1, padx=10, pady=10)
        
        # 锁控制器ID（可选）
        tk.Label(add_window, text="锁控制器ID (可选):").grid(row=3, column=0, padx=10, pady=10, sticky=tk.W)
        lock_controller_id_var = tk.StringVar()
        tk.Entry(add_window, textvariable=lock_controller_id_var, width=30).grid(row=3, column=1, padx=10, pady=10)
        
        # 子锁号（可选）
        tk.Label(add_window, text="子锁号 (可选):").grid(row=4, column=0, padx=10, pady=10, sticky=tk.W)
        sub_lock_number_var = tk.StringVar()
        tk.Entry(add_window, textvariable=sub_lock_number_var, width=30).grid(row=4, column=1, padx=10, pady=10)
        
        # 提交按钮
        def submit():
            scooter_id = scooter_id_var.get().strip()
            scooter_name = scooter_name_var.get().strip()
            bluetooth_address = bluetooth_address_var.get().strip()
            lock_controller_id = lock_controller_id_var.get().strip() or None
            sub_lock_number_str = sub_lock_number_var.get().strip()
            sub_lock_number = int(sub_lock_number_str) if sub_lock_number_str else None
            
            if not scooter_id or not scooter_name or not bluetooth_address:
                messagebox.showerror("错误", "车辆ID、名称和蓝牙地址为必填项", parent=add_window)
                return
            
            # 添加车辆
            success = self.scooter_controller.register_scooter(
                scooter_id, scooter_name, bluetooth_address, lock_controller_id, sub_lock_number
            )
            
            if success:
                messagebox.showinfo("成功", "车辆添加成功", parent=add_window)
                add_window.destroy()
                self.refresh_scooter_list()
            else:
                messagebox.showerror("错误", "车辆添加失败，可能是ID或蓝牙地址已存在", parent=add_window)
        
        tk.Button(add_window, text="提交", command=submit).grid(row=5, column=0, columnspan=2, pady=20)
    
    # 新增方法：锁管理相关
    def refresh_lock_list(self):
        """刷新锁控制器列表"""
        # 清空现有数据
        for item in self.lock_tree.get_children():
            self.lock_tree.delete(item)
        
        # 获取所有锁控制器
        controllers = self.scooter_controller.lock_manager.get_all_lock_controllers()
        
        # 添加到列表
        for controller in controllers:
            self.lock_tree.insert("", tk.END, values=(
                controller["controller_id"],
                controller["controller_name"],
                controller["mqtt_topic_prefix"],
                controller["status"]
            ))
    
    def add_lock_controller(self):
        """添加新的锁控制器"""
        # 弹出窗口获取信息
        add_window = tk.Toplevel(self.root)
        add_window.title("添加新锁控制器")
        add_window.geometry("400x200")
        
        # 控制器ID
        tk.Label(add_window, text="控制器ID:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        controller_id_var = tk.StringVar()
        tk.Entry(add_window, textvariable=controller_id_var, width=30).grid(row=0, column=1, padx=10, pady=10)
        
        # 控制器名称
        tk.Label(add_window, text="控制器名称:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        controller_name_var = tk.StringVar()
        tk.Entry(add_window, textvariable=controller_name_var, width=30).grid(row=1, column=1, padx=10, pady=10)
        
        # MQTT主题前缀
        tk.Label(add_window, text="MQTT主题前缀:").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
        mqtt_topic_prefix_var = tk.StringVar()
        tk.Entry(add_window, textvariable=mqtt_topic_prefix_var, width=30).grid(row=2, column=1, padx=10, pady=10)
        
        # 提交按钮
        def submit():
            controller_id = controller_id_var.get().strip()
            controller_name = controller_name_var.get().strip()
            mqtt_topic_prefix = mqtt_topic_prefix_var.get().strip()
            
            if not controller_id or not controller_name or not mqtt_topic_prefix:
                messagebox.showerror("错误", "所有字段均为必填项", parent=add_window)
                return
            
            # 添加锁控制器
            success = self.scooter_controller.register_lock_controller(
                controller_id, controller_name, mqtt_topic_prefix
            )
            
            if success:
                messagebox.showinfo("成功", "锁控制器添加成功", parent=add_window)
                add_window.destroy()
                self.refresh_lock_list()
            else:
                messagebox.showerror("错误", "锁控制器添加失败，可能是ID或MQTT主题前缀已存在", parent=add_window)
        
        tk.Button(add_window, text="提交", command=submit).grid(row=3, column=0, columnspan=2, pady=20)
    
    def test_unlock(self):
        """测试解锁指定的锁"""
        # 获取选中的锁控制器
        selected_items = self.lock_tree.selection()
        if not selected_items:
            messagebox.showerror("错误", "请先选择一个锁控制器")
            return
        
        # 获取锁控制器信息
        item = selected_items[0]
        controller_id = self.lock_tree.item(item, "values")[0]
        
        # 弹出窗口获取子锁号
        sub_lock_number = simpledialog.askinteger("子锁号", "请输入要测试的子锁号 (1-5):", minvalue=1, maxvalue=5)
        if sub_lock_number is None:
            return
        
        # 显示进度提示
        progress_window = tk.Toplevel(self.root)
        progress_window.title("解锁中")
        progress_window.geometry("300x100")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        progress_label = tk.Label(progress_window, text=f"正在解锁 {controller_id} 的子锁 {sub_lock_number}...\n请稍候")
        progress_label.pack(pady=20)
        
        # 执行解锁
        def run_unlock():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.scooter_controller.mqtt_controller.async_unlock(controller_id, sub_lock_number))
                loop.close()
                
                # 更新UI需在主线程中进行
                self.root.after(0, lambda: self.show_unlock_result(result, controller_id, sub_lock_number, progress_window))
            except Exception as e:
                # 发生异常时，在主线程中显示错误
                error_msg = str(e)
                self.root.after(0, lambda: self.show_unlock_error(error_msg, controller_id, sub_lock_number, progress_window))
        
        threading.Thread(target=run_unlock).start()
    
    def show_unlock_result(self, result, controller_id, sub_lock_number, progress_window=None):
        """显示解锁结果"""
        # 关闭进度窗口
        if progress_window:
            progress_window.destroy()
            
        if result:
            messagebox.showinfo("成功", f"成功解锁 {controller_id} 的子锁 {sub_lock_number}")
            # 记录到日志
            self.log_output.insert(tk.END, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 成功解锁 {controller_id} 的子锁 {sub_lock_number}\n")
            self.log_output.see(tk.END)
        else:
            messagebox.showerror("错误", f"解锁 {controller_id} 的子锁 {sub_lock_number} 失败")
            # 记录到日志
            self.log_output.insert(tk.END, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 解锁 {controller_id} 的子锁 {sub_lock_number} 失败\n")
            self.log_output.see(tk.END)
    
    def show_unlock_error(self, error_msg, controller_id, sub_lock_number, progress_window=None):
        """显示解锁过程中的错误"""
        # 关闭进度窗口
        if progress_window:
            progress_window.destroy()
            
        messagebox.showerror("错误", f"解锁 {controller_id} 的子锁 {sub_lock_number} 时发生错误:\n{error_msg}")
        # 记录到日志
        self.log_output.insert(tk.END, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 解锁错误: {error_msg}\n")
        self.log_output.see(tk.END)

    def add_auto_update_history_button(self):
        """添加一个按钮，用于查看自动更新历史记录"""
        self.auto_update_button = tk.Button(
            self.device_frame, 
            text="查看自动更新记录", 
            command=self.show_auto_update_history
        )
        self.auto_update_button.pack(pady=5)
    
    def show_auto_update_history(self):
        """显示自动更新的历史记录"""
        # 创建新窗口
        history_window = tk.Toplevel(self.root)
        history_window.title("自动更新历史记录")
        history_window.geometry("800x400")
        
        # 创建 Treeview 用于显示历史记录
        columns = ("操作时间", "车辆ID", "锁控制器ID", "子锁号", "状态")
        history_tree = ttk.Treeview(history_window, columns=columns, show="headings")
        
        # 设置列标题
        for col in columns:
            history_tree.heading(col, text=col)
            history_tree.column(col, width=150)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=history_tree.yview)
        history_tree.configure(yscrollcommand=scrollbar.set)
        history_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 获取最近的操作记录
        logs = self.scooter_controller.get_operation_logs(limit=50)
        
        # 过滤出锁定操作后紧接着发生关联更新的记录
        auto_update_logs = []
        update_times = {}
        
        # 首先找出所有更新操作的时间
        for log in logs:
            if log['operation_type'] == "更新关联":
                scooter_id = log['scooter_id']
                update_times[scooter_id] = log['operation_time']
        
        # 然后找出所有锁定操作后紧接着发生更新的记录
        for log in logs:
            if log['operation_type'] == "锁定":
                scooter_id = log['scooter_id']
                if scooter_id in update_times:
                    lock_time = datetime.fromisoformat(log['operation_time'])
                    update_time = datetime.fromisoformat(update_times[scooter_id])
                    
                    # 如果更新时间在锁定后的5分钟内
                    if (update_time - lock_time).total_seconds() <= 300:
                        auto_update_logs.append({
                            "操作时间": update_times[scooter_id],
                            "车辆ID": scooter_id,
                            "锁控制器ID": log['controller_id'],
                            "子锁号": log['sub_lock_number'],
                            "状态": "自动更新"
                        })
        
        # 将自动更新记录显示在树形视图中
        for i, log in enumerate(auto_update_logs):
            values = (log["操作时间"], log["车辆ID"], log["锁控制器ID"], log["子锁号"], log["状态"])
            history_tree.insert("", "end", iid=i, values=values)

if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop() 
    