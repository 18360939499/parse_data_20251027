import socket
import struct
import threading
import numpy as np
import time
import datetime
import psutil  # 用于检查内存使用情况
import requests
import base64
import re
import pymysql
import json
import queue

# ---------------------------------------------------------------------------------
# 与前端的接口


from flask import Flask, request, jsonify, render_template
from flask_cors import CORS, cross_origin
from collections import deque
from scipy.ndimage import convolve
from flask_compress import Compress

app1 = Flask(__name__)
CORS(app1)  # 允许所有域名的CORS请求
Compress(app1)

MAX_RADAR_LEN = (0x399650) #(0x02C204)#测试当雷达发送一帧数据大于MAX_RADAR_LEN时，可以不缺数据的接收，如果少于呢
UPLOAD_INTERVAL_SECOND=1 #20min
PRINT_TIME_INTERVAL_SECOND=10


# 线程存储
threads = {}
threads_lock = threading.Lock()

buf_lock = threading.Lock() #给 buf_data 加锁（必须）

# 数据库连接信息
try:
    db = pymysql.connect(
        host="47.97.38.203",
        user="root",
        password="AZDazd20230928@",
        database="csv",
        charset="utf8mb4"
    )
    print("数据库连接成功")
except pymysql.OperationalError as e:
    if e.args[0] == 2003:
        print("错误 2003：无法连接到 MySQL 服务器，可能是网络、防火墙或bind-address问题")
    elif e.args[0] == 1045:
        print("错误 1045：用户名或密码错误，或者没有远程访问权限")
    else:
        print(f"MySQL OperationalError: {e}")
    exit()
except pymysql.MySQLError as e:
    print(f"MySQL 错误: {e}")
    exit()
except socket.timeout:
    print("连接超时，可能 MySQL 没有响应或端口被阻止")
    exit()
except Exception as e:
    print(f"其他错误: {e}")
    exit()

def insert_data(latest_original_data, latest_point_data):
    try:
        with db.cursor() as cursor:
            matrix_bytes = pymysql.Binary(bytes(latest_original_data))  # 转成bytes再包装
            matrix_str = latest_point_data

            sql = "INSERT INTO test20260527liuqiao (matrix_original, speed) VALUES (%s, %s)"
            cursor.execute(sql, (matrix_bytes, matrix_str))
            db.commit()
    except pymysql.MySQLError as e:
        print(f"数据库操作失败: {e}")

ready_to_upload_data_queue = queue.Queue()  # 全局队列

def periodic_db_upload():
    while True:
        # time.sleep(UPLOAD_INTERVAL_SECOND)

        # 从队列取数据（没有就不执行）
        if not ready_to_upload_data_queue.empty():
            try:
                original_data, to_web = ready_to_upload_data_queue.get()# 取出一条
                insert_data(original_data, to_web)# 上传
                # print(f"saved to db:{to_web}", flush=True)
                print(to_web,"tdb", flush=True)
            except Exception as e:
                print(f"[定时上传] 失败: {e}")   

buf_data = bytearray()
radar = None
connect_state = 0
# 缓冲区大小阈值
buf_data_threshold = 10 * MAX_RADAR_LEN  # 10帧数据的大小

# 调整缓冲区大小的阈值
memory_threshold = 0.8  # 80% 内存使用率

def run_time_thread():
    while True:
        timethread()
        time.sleep(PRINT_TIME_INTERVAL_SECOND) #testxy_time.sleep(10)#0.1也可以

def timethread():
    time2 = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(time2, len(buf_data),flush=True)


def run_up_data_thread():
    while True:
        up_data_thread()
        time.sleep(0.2) #testxy_time.sleep(9.8)

def get_packet_header(header_bArr):
    header_struct = "<HHHHIIIII"
    header_unpack = struct.unpack(header_struct, header_bArr)

    header = {
        "syncWord": [hex(header_unpack[0]), hex(header_unpack[1]), hex(header_unpack[2]), hex(header_unpack[3])],
        "frameId": header_unpack[4],
        "coreId": header_unpack[5],
        "TLVNums": header_unpack[6],
        "totalLength": header_unpack[7],
        "detectObjNums": header_unpack[8]
    }

    return header

def up_data_thread():
    global buf_data  # 相当于一个缓存，存放还未处理的雷达数据
    # global frame_len
    # 动态调整缓冲区大小
    memory_usage = psutil.virtual_memory().percent / 100.0
    if memory_usage > memory_threshold:
        buf_data_threshold = 5 * MAX_RADAR_LEN  # 临时减少最大缓冲区大小以腾出空间
    else:
        buf_data_threshold = 10 * MAX_RADAR_LEN  # 恢复默认缓冲区大小

    with buf_lock:

        # 数据流控制
        if len(buf_data) >= buf_data_threshold:
            print("缓冲区已满，暂停接收数据", len(buf_data),flush=True)
            buf_data.clear()
            return

        if len(buf_data) >= MAX_RADAR_LEN:  # 170000
            packet_header_size = 28
            sync_word = b'\x02\x01\x04\x03\x06\x05\x08\x07'
            start_idx = buf_data.find(sync_word)
            if start_idx == -1:# 未找到数据同步帧头，清空当前缓冲区数据
                print("未找到数据同步帧头，清空当前缓冲区数据", len(buf_data),flush=True)
                buf_data.clear()
                return

            packet_header = get_packet_header(buf_data[start_idx:start_idx + packet_header_size])

            if start_idx+packet_header["totalLength"]>len(buf_data):
                print(packet_header["frameId"],"not all",start_idx,len(buf_data),packet_header["totalLength"], flush=True)
                return
            print(packet_header["frameId"],"all",start_idx,len(buf_data), packet_header["totalLength"], flush=True)
            temp_original_data=buf_data[start_idx: start_idx + packet_header["totalLength"]]
            buf_data = buf_data[start_idx + packet_header["totalLength"]:]  # 清除上一帧的数据
            print( packet_header["frameId"],"clr",len(buf_data), flush=True)

            temp_to_web = packet_header["frameId"]
            ready_to_upload_data_queue.put((temp_original_data, temp_to_web))# 新数据放入队列

            print( packet_header["frameId"],'tque',flush=True)

class ServerThread:  # 用于启动tcp/ip服务端来接收雷达数据，启用保活功能，设置大缓存来保证大数据传输

    def __init__(self, ipaddr, port, num):
        self.ipaddr = ipaddr
        self.port = port
        self.num = num
        self.radar_conn = None  # 用成员变量，替代全局radar

    def server_link(self, conn, addr):
        global connect_state
        global buf_data
        connect_state = 1
        self.radar_conn = conn  # 绑定当前雷达连接

        print("5207，网关已经连接到服务器", flush=True)

        while True:
            try:
                data = conn.recv(1024 * 64)  # 之前是8K,更大缓冲区
                if not data:
                    break
                if len(buf_data) >= buf_data_threshold:
                    print("缓冲区已满，丢弃数据", flush=True)
                    continue
                with buf_lock:
                    buf_data.extend(data)
            
            except Exception as e:
                print(f"连接异常: {e}", flush=True)
                break
        conn.close()
        connect_state = 0
        self.radar_conn = None
        print("[INFO] 5207,网关断开连接", flush=True)

    def server_start(self):
        s_pro = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 64)

        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

        s_pro.bind((self.ipaddr, self.port))
        s_pro.listen(self.num)
        print('Waiting 5207 link...', flush=True)

        while True:
            conn, addr = s_pro.accept()
            print("新连接来自 ", addr, flush=True)
            p = threading.Thread(target=self.server_link, args=(conn, addr))
            if False:
                p.daemon = True  # 建议关闭，防止突然丢数据
            p.start()

    def send_data(self, data):# 现在这个方法可以正常使用了
        if self.radar_conn:
            try:
                self.radar_conn.send(data)
                print(f"发送数据成功: {len(data)} 字节")
            except Exception as e:
                print(f"发送失败: {e}")
        else:
            print("未连接雷达，无法发送")

def start_server():  # 启动flask框架线程
    app1.run(host='0.0.0.0')

WATCHDOG_INTERVAL = 600  # 看门狗检测间隔,单位秒 

server = None  # 全局保存TCP服务对象

def watchdog():
    """监控关键线程是否存活，若发现异常，则重启线程"""
    global threads
    global server  # 把server变成全局，才能真正重启

    while True:
        with threads_lock:  # 确保线程安全
            # 检查 TCP/IP 服务器线程：先看看 threads 字典里有没有存叫 tcp_ip_server 的线程
            #并且再看看这个线程是不是已经死了（不运行了）
            #如果两个条件都满足 → 进入重启逻辑
            if "tcp_ip_server" in threads and not threads["tcp_ip_server"].is_alive():
                print("[看门狗] TCP/IP 服务器线程已停止，正在重启...", flush=True)
                server = ServerThread('', 5207, 5)
                threads["tcp_ip_server"] = threading.Thread(target=server.server_start, daemon=True)
                threads["tcp_ip_server"].start()

           # 检查 时间处理线程
            if "time" in threads and not threads["time"].is_alive():
                print("[看门狗] 时间处理线程已停止，正在重启...", flush=True)
                threads["time"] = threading.Thread(target=run_time_thread, daemon=True)
                threads["time"].start()
                
            # 检查 矩阵处理线程
            if "up_data_matrix" in threads and not threads["up_data_matrix"].is_alive():
                print("[看门狗] 矩阵处理线程已停止，正在重启...", flush=True)
                threads["up_data_matrix"] = threading.Thread(target=run_up_data_thread, daemon=True)
                threads["up_data_matrix"].start()

            # ===================== 定时上传线程 =====================
            if "periodic_upload" in threads and not threads["periodic_upload"].is_alive():
                print("[看门狗] periodic_db_upload 已停止，正在重启...", flush=True)
                threads["periodic_upload"] = threading.Thread(target=periodic_db_upload, daemon=True)
                threads["periodic_upload"].start()

        # 异步检查 Flask API
        threading.Thread(target=check_flask_api, daemon=True).start()

        time.sleep(WATCHDOG_INTERVAL)


def check_flask_api():
    """检查 Flask API 是否存活"""
    try:
        response = requests.get("http://127.0.0.1:5007/api/get_matrix", timeout=3)
        if response.status_code != 200:
            print("[看门狗] Flask API 可能失去响应", flush=True)
    except requests.RequestException:
        print("[看门狗] 无法访问 Flask API", flush=True)

if __name__ == '__main__':
    with threads_lock:#我要开始用 threads 了，你们其他线程都先等一下，等我用完你们再用！

        # 启动 TCP/IP 服务器线程
        server = ServerThread('', 5207, 5)
        threads["tcp_ip_server"] = threading.Thread(target=server.server_start, daemon=True)
        threads["tcp_ip_server"].start()
        print("TCP/IP 服务器已启动")

        # 启动时间处理线程
        threads["time"] = threading.Thread(target=run_time_thread, daemon=True)
        threads["time"].start()
        print("时间处理线程已启动")

        # 启动矩阵处理线程
        threads["up_data_matrix"] = threading.Thread(target=run_up_data_thread, daemon=True)
        threads["up_data_matrix"].start()
        print("矩阵处理线程已启动")

        threads["periodic_upload"] = threading.Thread(target=periodic_db_upload, daemon=True)
        threads["periodic_upload"].start()
        print("定时数据库上传线程已启动")

        # 启动看门狗线程
        threads["watchdog"] = threading.Thread(target=watchdog, daemon=True)
        threads["watchdog"].start()
        print("看门狗线程已启动")

    # 启动 Flask，threaded=True 让其不会阻塞主线程
    app1.run(host='0.0.0.0', port=5007, threaded=True)

