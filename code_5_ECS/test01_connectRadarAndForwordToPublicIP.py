import socket
import threading
import time

# RADAR_IP = "192.168.1.100"
# RADAR_PORT = 5005

RADAR_IP = "192.168.1.200"
RADAR_PORT = 29172

SERVER_IP = "47.97.38.203"
SERVER_PORT = 5200

BUF_SIZE = 65535
MIN_FRAME_LEN = 29   # 最小帧长度

def forward(src, dst, filter_small_frame=False):
    try:
        while True:
            data = src.recv(BUF_SIZE)
            if not data:
                break

            # 只对“雷达 → 云端”方向做长度过滤
            if filter_small_frame and len(data) < MIN_FRAME_LEN:
                print(f"Drop frame: len={len(data)}")
                continue

            dst.sendall(data)

    except Exception as e:
        print("forward error:", e)

while True:
    try:
        print("Connecting to radar...")
        radar = socket.create_connection((RADAR_IP, RADAR_PORT))

        print("Connecting to server...")
        server = socket.create_connection((SERVER_IP, SERVER_PORT))

        print("Connected. Forwarding data...")

        # 雷达 → 云端（启用帧长度过滤）
        t1 = threading.Thread(
            target=forward,
            args=(radar, server, True),
            daemon=True
        )

        # 云端 → 雷达（不做过滤）
        t2 = threading.Thread(
            target=forward,
            args=(server, radar, False),
            daemon=True
        )

        t1.start()
        t2.start()

        t1.join()
        t2.join()

    except Exception as e:
        print("connection lost, retrying...", e)
        time.sleep(3)
