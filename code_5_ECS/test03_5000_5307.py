import socket
import threading
import time

RADAR_IP = "192.168.1.200"
RADAR_PORT = 5000

SERVER_IP = "47.97.38.203"
SERVER_PORT = 5307

BUF_SIZE = 65535
MIN_FRAME_LEN = 29

def forward(src, dst, name, filter_small_frame=False):
    try:
        while True:
            data = src.recv(BUF_SIZE)
            if not data:
                print(f"[{name}] 连接断开，无数据接收")
                break

            # 打印收到数据
            print(f"[{name}] 收到数据，长度: {len(data)} 字节")

            if filter_small_frame and len(data) < MIN_FRAME_LEN:
                print(f"[{name}] 丢弃过小帧: len={len(data)}")
                continue

            dst.sendall(data)

    except Exception as e:
        print(f"[{name}] 转发异常: {e}")

while True:
    try:
        print("\n===== 开始建立连接 =====")

        # 连接雷达
        print(f"正在连接雷达 {RADAR_IP}:{RADAR_PORT} ...")
        radar = socket.create_connection((RADAR_IP, RADAR_PORT))
        print("✅ 雷达连接成功！")

        # 连接服务器
        print(f"正在连接阿里云 {SERVER_IP}:{SERVER_PORT} ...")
        server = socket.create_connection((SERVER_IP, SERVER_PORT))
        print("✅ 阿里云服务器连接成功！")

        print("\n🚀 开始双向数据转发...")

        # 双线程转发
        t1 = threading.Thread(target=forward, args=(radar, server, "雷达→云端", True), daemon=True)
        t2 = threading.Thread(target=forward, args=(server, radar, "云端→雷达", False), daemon=True)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

    except Exception as e:
        print("❌ 连接失败或断开:", e)
        print("3秒后重试...\n")
        time.sleep(3)

# ===== 开始建立连接 =====
# 正在连接雷达 192.168.1.200:5000 ...
# ✅ 雷达连接成功！
# 正在连接阿里云 47.97.38.203:5307 ...
# ✅ 阿里云服务器连接成功！
#
# 🚀 开始双向数据转发...
# [云端→雷达] 收到数据，长度: 49 字节
# [云端→雷达] 收到数据，长度: 49 字节
# [雷达→云端] 收到数据，长度: 80 字节
# [雷达→云端] 转发异常: [WinError 10053] 你的主机中的软件中止了一个已建立的连接。