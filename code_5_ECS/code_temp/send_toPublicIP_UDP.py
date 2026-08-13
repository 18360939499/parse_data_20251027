import socket

SERVER_IP = "47.97.38.203"
SERVER_PORT = 812

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

hex_string = """
AA AA 00 00 00 00
1A 01 00
00 00 00 00
BC F4
55 55
"""

data = bytes.fromhex(hex_string)

sock.sendto(
    data,
    (SERVER_IP, SERVER_PORT)
)

print("发送完成")
print(f"目标: {SERVER_IP}:{SERVER_PORT}")
print(f"长度: {len(data)}")
print(f"HEX : {data.hex(' ').upper()}")

sock.close()