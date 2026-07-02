import socket
import os
from datetime import datetime

# ================== 参数配置 ==================
radar_ip_address = "192.168.1.200"
tcp_port_num = 29172
MAX_PACKET_SIZE_BYTES = 160000

# 单个文件最大大小：2GB
MAX_FILE_SIZE = 200  * 1024 * 1024
# MAX_FILE_SIZE = 2 * 1024 * 1024

# ================== 创建保存目录 ==================
timestamp = datetime.now().strftime("%Y_%m%d_%H%M_%S")
save_dir = "../../../../data"
os.makedirs(save_dir, exist_ok=True)

# ================== 文件创建函数 ==================
file_index = 1

def create_new_file():
    global file_index

    file_name = f"radar_raw_data_{timestamp}_{file_index:03d}.bin"
    file_path = os.path.join(save_dir, file_name)

    fid = open(file_path, "wb")

    print(f"\n创建新文件: {file_name}")

    file_index += 1

    return fid, file_path

# 创建第一个文件
fid, current_file_path = create_new_file()

# ================== TCP Socket ==================
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)

sock.connect((radar_ip_address, tcp_port_num))

sock.settimeout(0.2)

print("已连接雷达 TCP 数据流...")

# ================== 循环接收数据 ==================
try:
    while True:
        try:
            data = sock.recv(MAX_PACKET_SIZE_BYTES)

            if not data:
                print("连接关闭")
                break

            # 判断当前文件是否超过 2GB
            current_size = fid.tell()

            if current_size + len(data) > MAX_FILE_SIZE:
                fid.close()

                print(f"文件超过 2GB，切换新文件...")

                fid, current_file_path = create_new_file()

            # 写入数据
            fid.write(data)
            fid.flush()

            print(f"写入 {len(data)} 字节 -> 当前文件大小: {fid.tell() / (1024*1024):.2f} MB")

        except socket.timeout:
            continue

except KeyboardInterrupt:
    print("用户手动停止接收")

finally:
    fid.close()
    sock.close()

    print("文件已关闭，连接已断开")