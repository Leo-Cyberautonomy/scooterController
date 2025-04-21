#!/usr/bin/env python3
"""
电动滑板车控制器主程序入口
支持蓝牙控制车辆和MQTT控制车锁
"""
import os
import sys
import tkinter as tk
from src.ui.main_window import MainWindow

def main():
    """主函数，创建并运行GUI界面"""
    root = tk.Tk()
    root.geometry("800x600")
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    # 确保当前目录在项目根目录中
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    main() 