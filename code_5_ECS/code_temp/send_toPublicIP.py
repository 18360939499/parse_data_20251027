import socket
import time
import os

# SERVER_IP = "127.0.0.1"   "你的ECS公网IP"
SERVER_IP = "47.97.38.203"   #"你的ECS公网IP"

SERVER_PORT = 5200

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

sock.connect((SERVER_IP, SERVER_PORT))
print("✅ 已连接到 ECS 5200")

while True:
    data = os.urandom(8192)
    sock.sendall(data)
    print("➡️  已发送", len(data), "字节")
    time.sleep(0.05)

