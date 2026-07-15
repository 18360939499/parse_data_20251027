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

import atexit

app1 = Flask(__name__)
CORS(app1)  # 允许所有域名的CORS请求
Compress(app1)

MAX_RADAR_LEN = (0x39A320) #(0x399650) #测试当雷达发送一帧数据大于MAX_RADAR_LEN时，可以不缺数据的接收，如果少于呢
MAX_RADAR_TOTAL_LEN = 20000000 #一帧不会大于20M
SYNC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
HEADER_SIZE = 28
PORT_NUM = 5207
PRINT_TIME_INTERVAL_SECOND=10

RADAR_SEND_INTERVAL =10 #雷达发送时间间隔

buffer_data = bytearray()
raw_queue = queue.Queue(maxsize=2000)
frame_queue = queue.Queue(maxsize=2000)

thread_status = {
    "tcp": False,
    "parser": False,
    "db": False
}
status_lock = threading.Lock()


UPLOAD_BATCH_SIZE = 10
g_db_buffer = []
g_db_buffer_lock = threading.Lock()


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

def insert_data_batch(data_list):
    try:
        with db.cursor() as cursor:
            sql = "INSERT INTO test20260527liuqiao (matrix_original, speed) VALUES (%s, %s)"

            batch_values = []
            for original_data, to_web in data_list:
                original_data_bytes = pymysql.Binary(bytes(original_data))
                batch_values.append((original_data_bytes, to_web))

            cursor.executemany(sql, batch_values)
            db.commit()

    except pymysql.MySQLError as e:
        print(f"批量数据库失败: {e}")

def periodic_db_upload():
    global g_db_buffer

    while True:
        if frame_queue.empty():
            continue
        original_data, to_web = frame_queue.get(timeout=2)# 取出一条

        db_batch = None
        #放入缓存
        with g_db_buffer_lock:
            g_db_buffer.append((original_data, to_web))
            # print(f"app{to_web} ")
            if len(g_db_buffer)>=UPLOAD_BATCH_SIZE:
                db_batch = g_db_buffer
                g_db_buffer = []    #g_db_buffer.clear()
        if db_batch is not None:
            insert_data_batch(db_batch)
            print(f"db{len(db_batch)}",flush=True)         

def flush_db_buffer():
    global g_db_buffer

    with g_db_buffer_lock:
        if g_db_buffer:
            insert_data_batch(g_db_buffer)
            print(f"[DB] flush remaining {len(g_db_buffer)} frames")
            g_db_buffer.clear()

def parse_data_thread():
    global buffer_data

    while True:
        if raw_queue.empty():
            continue
         
        data = raw_queue.get()
        buffer_data.extend(data)

        while True:
            if len(buffer_data) < MAX_RADAR_LEN:
                break
            start_idx = buffer_data.find(SYNC_WORD)
            if start_idx == -1:# 未找到数据同步帧头，清空当前缓冲区数据
                print("未找到数据同步帧头，清空当前缓冲区数据", len(buffer_data),flush=True)
                buffer_data.clear()
                break
            if start_idx > 0:
                del buffer_data[:start_idx]
            
            if len(buffer_data) < HEADER_SIZE:
                break
            packet_header = get_packet_header(buffer_data[:HEADER_SIZE])

            frame_Id = packet_header["frameId"]
            frame_total_len = packet_header["totalLength"]

            #合法性校验
            if frame_total_len > MAX_RADAR_TOTAL_LEN:
                print("invalid frame len:", frame_total_len)
                buffer_data.clear()
                break
            if len(buffer_data) < frame_total_len:
                print(frame_Id,"not all",start_idx,len(buffer_data),frame_total_len, flush=True)
                break

            print(frame_Id,"al",start_idx,len(buffer_data), frame_total_len, flush=True)
            temp_original_data=buffer_data[:frame_total_len]
            del buffer_data[:frame_total_len]  # 清除上一帧的数据
            # print(frame_Id,"clr",len(buffer_data), flush=True)
            try:
                frame_queue.put((temp_original_data, frame_Id), timeout=2)
            except queue.Full:
                print("frame_queue full, drop frame")
            print(frame_Id,'tq',flush=True)

# 1. server（只负责 listen）
# 2. session（只负责 conn recv）
# 3. reconnect（只负责恢复）
def tcp_server(host='0.0.0.0', port=PORT_NUM):#监听所有网卡（0.0.0.0）

    while True:
        try:
            # 1. 创建监听socket（只做一次逻辑）
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)#允许端口复用,防止程序重启时报：Address already in use
            s.bind((host, port))
            s.listen(10)#最多允许 N 个客户端排队连接
                        
            print(f"{port} TCP Server started，Waiting client link...")

            # 2. 接受连接循环
            while True:
                conn, addr = s.accept()
                print("网关connected:", addr)
                conn.settimeout((RADAR_SEND_INTERVAL*3))#如果 N 秒没有 recv 数据 →抛 socket.timeout

                try:
                    # 3. 数据接收循环
                    while True:
                        data = conn.recv(65535)
                        if not data:#客户端断开（正常关闭），返回值为b''，会进入这里
                            print("[TCP] client closed connection")
                            break
                        raw_queue.put(data)

                except socket.timeout:# ❗只是“没数据”，不是断线
                    print("[TCP] recv timeout (no data)")   
                except Exception as e:
                    print("[TCP] recv error:", e)     
                finally:
                    # 4. 保证释放连接
                    try:
                        conn.close()
                    except:
                        pass
                    print("[TCP] connection closed, waiting new client")
        except Exception as e:
            print("[TCP] 服务器启动异常", e)
            time.sleep(2)


def safe_start(name, target):
    with status_lock:
        if thread_status.get(name):
            return
        thread_status[name] = True

    t = threading.Thread(target=target, daemon=True)
    t.start()

atexit.register(flush_db_buffer)#程序退出时调用 flush_db_buffer()，所有函数定义之后，main之前”最标准

if __name__ == "__main__":

    safe_start("tcp", tcp_server)
    safe_start("parser", parse_data_thread)
    safe_start("db", periodic_db_upload)

    while True:
        print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} ru")
        time.sleep(PRINT_TIME_INTERVAL_SECOND)
