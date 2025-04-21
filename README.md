# 电动滑板车控制器

这个程序用于通过蓝牙控制电动滑板车和通过MQTT控制车锁，支持车辆与车锁的关联管理。

## 功能特点

- **蓝牙设备扫描与连接**：自动发现并连接附近的电动滑板车
- **MQTT车锁控制**：通过MQTT协议控制车锁的解锁与锁定
- **车辆与锁管理**：管理车辆和车锁的关联关系
- **设备注册与配置**：添加新的车辆和锁控制器
- **操作日志记录**：记录所有车辆和锁操作
- **直接命令控制**：支持直接发送AT命令控制车辆

## 安装依赖

```bash
pip install bleak asyncio tkinter sqlite3
```

要使用MQTT功能，还需安装Mosquitto客户端：

**Windows**:
从 [Mosquitto官网](https://mosquitto.org/download/) 下载并安装客户端

**Linux**:
```bash
sudo apt-get install mosquitto-clients
```

**macOS**:
```bash
brew install mosquitto
```

## 运行程序

```bash
python main.py
```

## 使用方法

1. **设备管理**：
   - 点击"扫描设备"找到附近的滑板车
   - 输入BLE密码后连接设备
   - 连接成功后可查看设备GATT服务

2. **操作指令**：
   - 选择操作类型（解锁/上锁/查询）
   - 点击"执行"发送命令到连接的设备

3. **车辆管理**：
   - 添加新车辆并设置其蓝牙地址
   - 查看已注册车辆信息
   - 更新车辆关联的锁

4. **锁管理**：
   - 添加锁控制器
   - 设置MQTT主题
   - 测试锁控制

5. **反馈日志**：
   - 查看命令执行结果
   - 监控设备状态

## 注意事项

- 蓝牙通信依赖于系统蓝牙适配器正常工作
- MQTT功能依赖于Mosquitto客户端正确安装
- 首次运行会在当前目录创建SQLite数据库文件

## 开发者信息

项目基于Python 3.6+开发，使用了以下主要库：
- bleak：用于BLE蓝牙通信
- asyncio：提供异步IO支持
- tkinter：提供GUI界面
- sqlite3：本地数据存储 