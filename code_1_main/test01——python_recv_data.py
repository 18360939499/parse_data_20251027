import socket
import os
from datetime import datetime

# ================== 保存 bin 文件路径 =======-+===========
timestamp = datetime.now().strftime("%Y_%m%d_%H%M_%S")

save_bin_path = rf"..\..\data\radar_raw_data_{timestamp}.bin"

os.makedirs(os.path.dirname(save_bin_path), exist_ok=True)

try:
    fid = open(save_bin_path, "wb")  # 覆盖写入
except OSError:
    raise RuntimeError("无法创建 bin 文件")

# ================== TCP 连接参数 ==================
radar_ip_address = "192.168.1.200"
tcp_port_num = 29172
MAX_PACKET_SIZE_BYTES = 160000

# 创建 TCP Socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)  # 连接超时
sock.connect((radar_ip_address, tcp_port_num))
sock.settimeout(0.2)  # 读超时

print("已连接雷达 TCP 数据流...")

# ================== 循环接收数据 ==================
try:
    while True:
        try:
            data = sock.recv(MAX_PACKET_SIZE_BYTES)
            if not data:
                print("连接关闭")
                break

            # 写入 bin 文件
            fid.write(data)
            fid.flush()  # 确保及时写入
            print(f"写入 {len(data)} 字节")

        except socket.timeout:
            # 没有数据就继续等待
            continue

except KeyboardInterrupt:
    print("用户手动停止接收")

finally:
    fid.close()
    sock.close()
    print("文件已关闭，连接已断开")
