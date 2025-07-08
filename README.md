# 智能滑板车管理系统

一个集成蓝牙和MQTT控制功能的滑板车管理系统，用于管理智能滑板车车队和锁控制器。

## 功能特点

- **蓝牙控制**：通过BLE协议直接控制滑板车ECU
- **MQTT锁控制**：远程控制车辆物理锁
- **智能关联**：自动关联车辆与物理锁位
- **数据管理**：车辆信息、锁信息和操作日志的数据库管理
- **用户友好界面**：基于Tkinter的直观操作界面

## 系统要求

- Python 3.8+
- Windows 10+ 或 Linux 或 macOS
- 蓝牙适配器（支持BLE）
- 网络连接（MQTT通信）

## 安装

1. 克隆仓库
```bash
git clone https://github.com/yourusername/scooterController.git
cd scooterController
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

## 使用说明

1. 启动应用
```bash
python src/main.py
```

2. 管理车辆
   - 在"车辆管理"界面添加车辆信息
   - 系统会自动更新车辆与物理锁的关联关系

3. 操作控制
   - 选择设备并连接
   - 选择操作命令（如解锁、上锁）
   - 系统会自动执行相应控制命令

## 锁控制器映射

系统支持两个锁控制器，每个控制器有5个子锁：
- 锁编号1-5映射到控制器866846061120977的子锁1-5
- 锁编号6-10映射到控制器866846061051685的子锁1-5

## MQTT消息格式

系统监听`data_report`主题，消息格式示例：
```json
{
  "seq": 1234,
  "state": "1",
  "batteryLevel": 85,
  "signalStrength": 25,
  "NO": "1234567890123",
  "openType": 1,
  "SN": "D0020610490500511"
}
```

## 许可证

MIT 