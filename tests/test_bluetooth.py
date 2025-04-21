# 蓝牙模块测试 
import unittest
from src.bluetooth.command_handler import format_command, parse_response

class TestBluetooth(unittest.TestCase):
    def test_format_command(self):
        command = format_command("BKSCT", "1234", "0")
        self.assertEqual(command, "AT+BKSCT=1234,0\r\n")

    def test_parse_response(self):
        response = parse_response("+ACK:BKSCT,0")
        self.assertEqual(response, "BKSCT,0")

if __name__ == '__main__':
    unittest.main() 