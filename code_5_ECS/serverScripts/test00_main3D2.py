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

MAX_RADAR_LEN = (0x399650) #测试当雷达发送一帧数据大于MAX_RADAR_LEN时，可以不缺数据的接收，如果少于呢
SYNC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
HEADER_SIZE = 28
PORT_NUM = 5207
PRINT_TIME_INTERVAL_SECOND=10

buffer_data = bytearray()
raw_queue = queue.Queue(maxsize=2000)
frame_queue = queue.Queue(maxsize=2000)


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

def periodic_db_upload():
    while True:
        if not frame_queue.empty():
            try:
                original_data, to_web = frame_queue.get()# 取出一条
                insert_data(original_data, to_web)# 上传
                print(to_web,"tdb", flush=True)
            except Exception as e:
                print(f"[定时上传] 失败: {e}")   

def parse_data_thread():
    global buffer_data
    while True:
        data = raw_queue.get()
        buffer_data.extend(data)

        while True:
            start_idx = buffer_data.find(SYNC_WORD)
            if start_idx == -1:# 未找到数据同步帧头，清空当前缓冲区数据
                print("未找到数据同步帧头，清空当前缓冲区数据", len(buffer_data),flush=True)
                buffer_data.clear()
                break
            
            if len(buffer_data) < start_idx + HEADER_SIZE:
                break
            packet_header = get_packet_header(buffer_data[start_idx:start_idx + HEADER_SIZE])

            frame_Id = packet_header["frameId"]
            frame_total_len = packet_header["totalLength"]
            if len(buffer_data) < start_idx + frame_total_len:
                print(frame_Id,"not all",start_idx,len(buffer_data),frame_total_len, flush=True)
                break

            print(frame_Id,"all",start_idx,len(buffer_data), frame_total_len, flush=True)
            temp_original_data=buffer_data[start_idx: start_idx + frame_total_len]
            buffer_data = buffer_data[start_idx + frame_total_len:]  # 清除上一帧的数据
            print(frame_Id,"clr",len(buffer_data), flush=True)
            frame_queue.put((temp_original_data, frame_Id))# 新数据放入队列
            print(frame_Id,'tque',flush=True)

def tcp_server(host='0.0.0.0', port=PORT_NUM):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)
    print(port,"TCP Server started，Waiting link...")

    conn, addr = s.accept()
    print("网关connected:", addr)
    conn.settimeout(10)

    while True:
        try:
            data = conn.recv(65535)
            if not data:
                break
            raw_queue.put(data)
        except Exception as e:
            print("TCP error:", e)
            break

if __name__ == "__main__":

    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=parse_data_thread, daemon=True).start()
    threading.Thread(target=periodic_db_upload, daemon=True).start()

    while True:
        print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} running")
        time.sleep(PRINT_TIME_INTERVAL_SECOND)




# 线程存储
threads = {}
threads_lock = threading.Lock()


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