# 密码管理

def change_ble_password(client, old_password, new_password):
    """
    修改设备的BLE密码。
    :param client: BLE客户端。
    :param old_password: 旧密码。
    :param new_password: 新密码。
    """
    command = f"AT+BKPWD={old_password},{new_password}\r\n"
    response = client.write_gatt_char("00002c01-0000-1000-8000-00805f9b34fb", command.encode())
    if response:
        print("密码修改成功")
    else:
        print("密码修改失败") 