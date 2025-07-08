# AT命令处理模块

def format_command(command_type, *args):
    """
    格式化AT命令。
    :param command_type: 命令类型，如"BKSCT"。
    :param args: 命令参数。
    :return: 格式化后的命令字符串。
    """
    command = f"AT+{command_type}=" + ",".join(map(str, args))
    return command

def parse_response(response):
    """
    解析设备返回的响应。
    :param response: 设备返回的响应字符串。
    :return: 解析后的结果。
    """
    if response.startswith("+ACK:BKINF,"):
        # 去掉前缀和尾部的 "$"
        content = response[len("+ACK:BKINF,"):].rstrip("$")
        parts = content.split(",")
        if len(parts) >= 7:
            lock_status = parts[0].strip()
            scooter_speed = parts[1].strip()
            current_mileage = parts[2].strip()
            total_mileage = parts[3].strip()
            ride_time = parts[4].strip()
            battery_percentage = parts[5].strip()
            headlamp_status = parts[6].strip()

            return (f"锁状态: {'解锁' if lock_status=='0' else '锁定'}, "
                    f"速度: {scooter_speed} km/h, "
                    f"当前里程: {current_mileage} km, "
                    f"总里程: {total_mileage} km, "
                    f"骑行时长: {ride_time} s, "
                    f"电量: {battery_percentage}%, "
                    f"头灯状态: {'关闭' if headlamp_status=='0' else '开启'}")
        else:
            return "响应格式错误"
    elif response.startswith("+ACK:"):
        # 其它命令返回，去掉前缀和尾部可能的 "$"
        return response.split(":", 1)[1].rstrip("$")
    else:
        return "未知响应" 