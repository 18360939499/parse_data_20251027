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

MAX_RADAR_LEN = 0x416EA8  # 170000

matrix_history = deque(maxlen=5)
threshold_z = 0.3
threshold_f = -1.2
H = 5
N = 5
A = 45
width1 = 40
width2 = 0.01
long = 5
radar_range2 = 6
latest_avg_value = 0
latest_matrix = None
latest_matrix2 = None
original_data = None
to_web = None
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


@app1.route('/')
def home():
    return render_template('刘桥站-右-水上.html')  # 返回HTML页面


@app1.route('/api/submit', methods=['POST'])
@cross_origin()
def submit_data():
    global radar_cycle
    global radar_range
    global radar_range2
    data = request.get_json()
    radar_cycle = data.get('cycle')
    radar_range = data.get('range')
    radar_range2 = radar_range
    print(f'雷达周期: {radar_cycle}, 雷达范围: {radar_range}', flush=True)
    sum_result = radar_cycle + radar_range
    # radar.send("sum_result".encode())
    setting()
    return jsonify({'status': 'success', 'cycle': radar_cycle, 'range': radar_range, 'sum': sum_result})


@app1.route('/get_temperature', methods=['GET'])
def get_temperature():
    global board_temperature

    temperature = board_temperature / 1000 + abs(board_temperature % 1000 / 1000)
    print(f'温度: {temperature}')
    return jsonify({'temperature': temperature})


@app1.route('/get_eva', methods=['GET'])
def get_eva():
    global buf_data5400, e_num, a_num, v_num

    print(e_num, a_num, v_num)
    a33 = e_num
    b33 = a_num
    c33 = v_num
    print(a33, b33, c33)
    return jsonify({
        'electricity': e_num,
        'alarm': a_num,
        'voltage': v_num
    })


@app1.route('/api/submit2', methods=['POST'])
def submit_data2():
    data = request.get_json()
    initial_row = data.get('initial')
    last_row = data.get('last')
    setRA()
    print(f'起始行数: {initial_row}, 末尾行数: {last_row}')

    return jsonify({'status': 'success', 'initial': initial_row, 'last': last_row})


@app1.route('/api/submit3', methods=['POST'])
def submit_data3():
    global Radar_h
    global Matrix_n
    global Positive_i
    global Negative_i
    global matrix_history
    global threshold_z
    global threshold_f
    global H
    global N
    global A
    data = request.get_json()

    Radar_h = float(data.get('Radar_h', 0))
    Matrix_n = int(data.get('Matrix_n', 10))
    Positive_i = float(data.get('Positive_i', 0))
    Negative_i = float(data.get('Negative_i', 0))
    angle_ab = int(data.get('angle_ab', 0))

    print(
        f'雷达高度: {Radar_h}, 岸边角度: {angle_ab},矩阵数: {Matrix_n},正插值阈值: {Positive_i}, 负插值阈值: {Negative_i}')

    matrix_history = deque(maxlen=Matrix_n)  # 更新 matrix_history 的 maxlen 为 Matrix_n
    threshold_z = Positive_i  # 更新正插值阈值
    threshold_f = Negative_i  # 更新负插值阈值
    H = Radar_h
    N = Matrix_n
    A = angle_ab
    return jsonify(
        {'status': 'success', '雷达高度': Radar_h, '岸边角度': angle_ab, '矩阵数': Matrix_n, '正插值阈值': Positive_i,
         '负插值阈值': Negative_i})


@app1.route('/api/submit4', methods=['POST'])
def submit_data4():
    global width1
    global width2
    global long

    data = request.get_json()

    river_d1 = float(data.get('river_d1', 0))

    river_d2 = float(data.get('river_d2', 0))
    r_r_long = float(data.get('r_r_long', 0))

    print(f'缆道端点距离（远）: {river_d1}, 缆道端点距离（近）: {river_d2},雷达与缆道距离: {r_r_long}')

    width1 = river_d1
    width2 = river_d2
    long = r_r_long
    return jsonify(
        {'status': 'success', '缆道端点距离（远）': river_d1, '缆道端点距离（近）': river_d2, '雷达与缆道距离': r_r_long})


@app1.route('/api/receive_bytes', methods=['POST'])
def receive_bytes():
    global restart_byte_data

    # 获取前端传送的Base64字符串
    base64_data = request.json.get('data')

    # 将Base64字符串解码为字节数据
    restart_byte_data = base64.b64decode(base64_data)
    send_restart_bytes(restart_byte_data)

    print(f"Received byte data: ", restart_byte_data.hex())
    # 可以在这里进行一些处理，例如返回处理结果
    return jsonify({"message": "Byte data received", "data": restart_byte_data.hex()})


@app1.route('/api/get_matrix', methods=['GET'])
def get_matrix():
    global to_web
    global Matrix_n
    global matrix_history, threshold_z, threshold_f, H, N, A
    global width1
    global width2
    global long
    global radar_range2
    global latest_avg_value
    # global latest_matrix
    global latest_matrix2
    # 生成一个随机矩阵
    matrix1 = to_web

    return jsonify({
        "matrixx": matrix1.tolist(),
        "mean_value": 0
    })


def find_ij_pairs(L):
    global width1
    global width2
    global long
    valid_pairs = []
    J1 = compute_j_first(width1, long)

    J2 = compute_j_first(width2, long)

    for i in range(1, 129):  # 0 < i < 128
        R = i * (50 / 128)  # 计算 R

        for j in range(J2, J1):  # 0 < j < 256
            angle = (np.pi / 4) + np.arcsin(j / 128 - 1)  # 计算角度

            R_cos = R * np.cos(angle)  # 计算 R * cos(θ)

            if np.isclose(R_cos, L, atol=1e-1):  # 允许微小误差
                valid_pairs.append((i, j))

    return valid_pairs


def compute_j_first(W, L):
    if L == 0:
        raise ValueError("L 不能为 0，否则会导致除零错误")

    angle = np.arctan(W / L)  # 计算 arctan(W/L)
    target_angle = angle - np.pi / 4  # 计算 pi/4 - arctan(W/L)
    sin_value = np.sin(target_angle)  # 计算 sin(pi/4 - arctan(W/L))

    j = (1 + sin_value) * 128  # 计算 j 值

    return int(j)  # 返回整数 j（四舍五入）


def insert_data(latest_original_data, latest_point_data):
    try:
        with db.cursor() as cursor:
            matrix_bytes = pymysql.Binary(bytes(latest_original_data))  # 转成bytes再包装

            matrix_rounded = np.round(latest_point_data, 2)
            matrix_str = json.dumps(matrix_rounded.tolist())

            sql = "INSERT INTO v_data (matrix_original, speed) VALUES (%s, %s)"
            cursor.execute(sql, (matrix_bytes, matrix_str))
            db.commit()
            print(f"已上传字节流和矩阵数据")
    except pymysql.MySQLError as e:
        print(f"数据库操作失败: {e}")


def periodic_db_upload():
    global original_data
    global to_web

    while True:
        time.sleep(60)  # 每300秒（5分钟）执行一次
        if original_data is not None and to_web is not None:
            try:
                insert_data(original_data, to_web)
                print(f"[定时上传] 已上传 ")
            except Exception as e:
                print(f"[定时上传] 上传失败: {e}")


# ---------------------------------------------------------------------------------


m6 = '000000070000000C0000004E0080008007D00032'  # 发送参数的尾部数据
m30 = '0000000200000005000000290080008013880019'
# m50 = '0000000200000004000000260080008017700012'  # 128rangebin
m50 = '000000030000000400000026008000800FA0000C'

m100 = '00000002000000040000003A0040010017700009'  # 256rangebin
m150 = '00000002000000030000001E004001002710000A'
m210 = '0000000200000004000000170040010036B0000A'
m300 = '0000000200000004000000230040010027100005'
m420 = '0000000200000004000000190040010036B00005'

systeminfo = {  # 默认的参数配置，以后可以根据默认文件来读取
    "rangeRes": 0.0471313931,
    "dopplerRes": 0.017786909,  # 有多个接收天线
    "numRangeBins": 128,  # 更改doppler与range点数后  要修改的起始参数
    "numDopplerBins": 128,  # 更改doppler与range点数后  要修改的起始参数
    "numSensors": 4,
    "numTxAnt": 3,
    "numRxAnt": 4,
    "numTxAzimuthAnt": 0,
    "numTxElevationAnt": 0,
    "padding": [0, 0, 0],
    "board_temperature": 0,
    "length": 65536
}

board_temperature = 0

buf_data = bytearray()
buf_data5300 = bytearray()
buf_data5400 = bytearray()

be_save = bytearray()  # 更改doppler与range点数后  要修改的起始参数
radar_data = np.zeros((256, 128))  # 继承自be_save
to_web = np.zeros((1, 100))  # 准备给前端的矩阵

radar = None
radar5300 = None
radar5400 = None

radar_cycle = '1000'
radar_cycle_old = '1000'
radar_range_old = '6'
radar_range = '6'

connect_state = 0
connect_state5300 = 0
connect_state5400 = 0

starting_rows = 0
starting_rows_old = 0
ending_rows = systeminfo['numRangeBins'] - 1
ending_rows_old = systeminfo['numRangeBins'] - 1

staring_angles = 0
staring_angles_old = 0
ending_angles = 255
ending_angles_old = 255
frame_len = 251216

# 缓冲区大小阈值
buf_data_threshold = 10 * MAX_RADAR_LEN  # 10帧数据的大小

# 调整缓冲区大小的阈值
memory_threshold = 0.8  # 80% 内存使用率


# -------------------------------------------------------------------------------------------------------------------------

def run_time_thread():
    while True:
        timethread()
        time.sleep(10)


def timethread():
    time2 = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(time2, flush=True)


def run_up_data_thread():
    while True:
        up_data_thread()
        time.sleep(9.8)


def up_data_thread():
    global buf_data  # 相当于一个缓存，存放还未处理的雷达数据
    global be_save  # 存放一帧数据
    global systeminfo
    global radar_data  # 继承自be_save
    global to_web
    global latest_matrix
    # global frame_len
    # 动态调整缓冲区大小
    memory_usage = psutil.virtual_memory().percent / 100.0
    if memory_usage > memory_threshold:
        buf_data_threshold = 5 * MAX_RADAR_LEN  # 临时减少最大缓冲区大小以腾出空间
    else:
        buf_data_threshold = 10 * MAX_RADAR_LEN  # 恢复默认缓冲区大小

    # 数据流控制
    if len(buf_data) >= buf_data_threshold:
        buf_data.clear()
        print("缓冲区已满，暂停接收数据", flush=True)

        return

    if len(buf_data) >= 4269400:  # 170000

        print("buf_data的长度", len(buf_data), flush=True)

        flag, buf_data = read_radar_data(buf_data)

        if (flag != 0xFF):
            return;
        # ----------------------------------------------------丢掉修改完参数的残留数据
        # point_arr = parse_be_save(be_save)

        buf_data = buf_data[MAX_RADAR_LEN:]  # 清除上一帧的数据

        to_web = 0

        print('已更新雷达数据', flush=True)


def read_radar_data(recv_buf_data):
    # header_size = 100
    header_size = 80
    radar_data_size = 65536
    # all_data = 65636
    # all_data = 65600
    global radar_data
    global be_save
    global systeminfo
    global board_temperature
    global original_data
    global frame_len
    head_word = b'\x01\x00\x00\x00\x21\x43\xCD\xAB'
    sync_word = b'\x02\x01\x04\x03\x06\x05\x08\x07'
    frame_head = b'\x1C\x00\x00\x00\x90\x01\x00\x00'
    frame_length = 184  # 单位：字节
    start_idx = recv_buf_data.find(sync_word)

    if start_idx == -1:
        # 未找到数据同步帧头，清空当前缓冲区数据
        flag = 2
        recv_buf_data.clear()
        print(f"flag: {flag}")
        return flag, recv_buf_data
    else:
        # frame_len_bytes = recv_buf_data[start_idx + 12 : start_idx + 16]
        # frame_len = struct.unpack('<I', frame_len_bytes)[0]  # 小端无符号整数
        # print("解析出的帧长度:", frame_len)

        if len(recv_buf_data) < MAX_RADAR_LEN:
            flag = 11  # 数据不完整
            print(f"flag: {flag}")
            return flag, recv_buf_data  # 保留数据等下一轮接收
        else:
            original_data = recv_buf_data[start_idx:start_idx + MAX_RADAR_LEN]
            print("original_data的长度", len(original_data), flush=True)

        # 当前buf数据未包含一个完整header，返回继续读取
        if len(recv_buf_data) < header_size:
            flag = 3
            print(f"flag: {flag}")
            return flag, recv_buf_data

        # 当前buf数据未包含一个完整header，返回继续读取
        else:
            recv_buf_data = recv_buf_data[start_idx:]
            systeminfo_bf = recv_buf_data[36:80]

            # 如果读取的数据长度不符合预期，打印错误并返回
            if len(systeminfo_bf) != 44:
                flag = 4
                print(f"flag: {flag}")
                return flag, recv_buf_data

            #####

            systeminfo = get_systeminfo(systeminfo_bf)
            # res = systeminfo['dopplerRes']
            # print(res)
            # print(systeminfo)
            board_temperature = systeminfo['board_temperature']
            lengthlength = systeminfo['length']
            print("lengthlength的长度", lengthlength, flush=True)

    flag = 0xFF
    recv_buf_data.clear()
    return flag, recv_buf_data


# def parse_be_save(be_save):
#     if not be_save or len(be_save) != 408:
#         print("be_save长度不正确或为空")
#         return np.array([])  # 返回空矩阵

#     data_bytes = be_save[8:]  # 跳过前8字节
#     # 直接一次性解包100个float（408 - 8 = 400字节，400/4=100个float）
#     float_tuple = struct.unpack('<100f', data_bytes)
#     arr = np.array(float_tuple)
#     arr = np.round(arr, 3)
#     return arr


def get_doppler_idx(gd_bArr):
    global systeminfo
    gd_struct = f"<{systeminfo['numRangeBins'] * 256}H"
    gd = np.array(struct.unpack(gd_struct, gd_bArr))
    return gd


def get_systeminfo(header_addr):  # 用来解析头部数据的函数

    header_struct = "<ffHHBBBBBBBBIHHHHHHII"

    header_unpack = struct.unpack(header_struct, header_addr)

    header = {
        "rangeRes": header_unpack[0],
        "dopplerRes": (header_unpack[1]) / 10,  # 有多个接收天线
        # "dopplerRes": (header_unpack[1]),
        "numRangeBins": header_unpack[2],
        "numDopplerBins": header_unpack[3],
        "numSensors": header_unpack[4],
        "numTxAnt": header_unpack[5],
        "numRxAnt": header_unpack[6],
        "numTxAzimuthAnt": header_unpack[7],
        "numTxElevationAnt": header_unpack[8],
        "padding": [header_unpack[9], header_unpack[10], header_unpack[11]],
        "board_temperature": header_unpack[12],
        "deal_range_start": header_unpack[13],
        "deal_range_end": header_unpack[14],
        "deal_angle_start": header_unpack[15],
        "deal_angle_end": header_unpack[16],
        "deal_angle_start2": header_unpack[17],
        "deal_angle_end2": header_unpack[18],
        "length": header_unpack[20]
    }
    return header


def exchange_left_right_matrix(array):  # 交换矩阵左右两半部分的函数，designed by 秦涛
    array1, array2 = np.split(array, 2, axis=1)
    array3 = np.hstack((array2, array1))
    return array3


def Polar_to_Rectangular(r, theta):  # 极坐标转直角坐标，输入的thata需为角度值,如果转换效果不及预期，调换x和y的位置  designed by 秦涛
    # theta = theta * (np.pi / 180)    #传进来的数值就是弧度单位的，所以不需要转换为弧度值
    for i in range(len(r)):
        for j in range(len(r[i])):
            y = r[i][j] * np.cos(theta[i][j])
            x = r[i][j] * np.sin(theta[i][j])
            r[i][j] = x
            theta[i][j] = y


# --------------------------------------------------------------------------------------------------------------------------------

def setting():  # 启动参数设置线程
    global radar_cycle
    global radar_range_old
    global radar_range
    global radar_cycle_old
    global systeminfo
    if radar_cycle != radar_cycle_old or radar_range != radar_range_old:
        header_cycle = myhex(radar_cycle)  # 周期转换为16进制32位
        if radar_range == '6':
            send_cycle_command_to_radar(header_cycle + m6)
            radar_cycle_old = radar_cycle
            radar_range_old = radar_range
            systeminfo['numRangeBins'] = 128
            print('已发送', radar_range, '参数', flush=True)
        elif radar_range == '30':
            send_cycle_command_to_radar(header_cycle + m30)
            radar_cycle_old = radar_cycle
            radar_range_old = radar_range
            systeminfo['numRangeBins'] = 128
            print('已发送', radar_range, '参数', flush=True)
        elif radar_range == '50':
            send_cycle_command_to_radar(header_cycle + m50)
            radar_cycle_old = radar_cycle
            radar_range_old = radar_range
            systeminfo['numRangeBins'] = 128
            print('已发送', radar_range, '参数', flush=True)
        elif radar_range == '100':
            send_cycle_command_to_radar(header_cycle + m100)
            radar_cycle_old = radar_cycle
            radar_range_old = radar_range
            systeminfo['numRangeBins'] = 256
            print('已发送', radar_range, '参数', flush=True)
        elif radar_range == '150':
            send_cycle_command_to_radar(header_cycle + m150)
            radar_cycle_old = radar_cycle
            radar_range_old = radar_range
            systeminfo['numRangeBins'] = 256
            print('已发送', radar_range, '参数', flush=True)
        elif radar_range == '210':
            send_cycle_command_to_radar(header_cycle + m210)
            radar_cycle_old = radar_cycle
            radar_range_old = radar_range
            systeminfo['numRangeBins'] = 256
            print('已发送', radar_range, '参数', flush=True)
        elif radar_range == '300':
            send_cycle_command_to_radar(header_cycle + m300)
            radar_cycle_old = radar_cycle
            radar_range_old = radar_range
            systeminfo['numRangeBins'] = 256
            print('已发送', radar_range, '参数', flush=True)
        elif radar_range == '420':
            send_cycle_command_to_radar(header_cycle + m420)
            radar_cycle_old = radar_cycle
            radar_range_old = radar_range
            systeminfo['numRangeBins'] = 256
            print('已发送', radar_range, '参数', flush=True)


# def setRA():
#     global starting_rows
#     global starting_rows_old
#     global ending_rows
#     global ending_rows_old

#     global staring_angles
#     global staring_angles_old
#     global ending_angles
#     global ending_angles_old
#     if starting_rows != starting_rows_old or ending_rows != ending_rows_old or staring_angles !=staring_angles_old or ending_angles !=ending_angles_old:
#         a = my8hex(starting_rows)
#         b = my8hex(ending_rows)
#         c = my8hex(staring_angles)
#         d = my8hex(ending_angles)
#         send_cycle_command_to_radar(a + b + c + d)
#         starting_rows_old = starting_rows
#         ending_rows_old = ending_rows
#         staring_angles_old = staring_angles
#         ending_angles_old = ending_angles
#         print('已发送选择的行数角度数')

def send_cycle_command_to_radar(cycle):
    global radar
    # rc, mid = send_command.publish_topic("/k1018dTtisV/cmdup/user/cmdup", bytearray(list(map(int, cycle))))
    # rc, mid = send_command.publish_topic("/k1018dTtisV/cmdup/user/cmdup", bytearray.fromhex(str.encode(cycle).hex()))
    # print(cycle)
    # print(str(cycle))
    radar.send(bytearray.fromhex(cycle))
    # rc, mid = send_command.publish_topic("/k1trkOHGXK4/cmdup/user/cmdup", bytearray.fromhex(cycle))
    print('发送成功', flush=True)


def send_restart_bytes(restart_bytes):
    global radar5300

    if radar5300:  # 检查是否连接
        try:
            radar5300.send(restart_bytes)  # 直接发送，不要 fromhex
            print('发送复位信息成功', flush=True)
        except Exception as e:
            print("发送失败:", e, flush=True)
    else:
        print("5300端口尚未连接，无法发送", flush=True)


def myhex(n):  # 整数转换成16进制32位，不够32位就补0
    n = int(n)  # 先转成int
    return "".join(f"{n:08x}")


def my8hex(n):  # 整数转换为16进制16位，不够16位就补零
    n = int(n)  # 先转成int
    return "".join(f"{n:04x}")


# -------------------------------------------------------------------------------------------------------------------------

class ServerThread:  # 用于启动tcp/ip服务端来接收雷达数据，启用保活功能，设置大缓存来保证大数据传输

    def __init__(self, ipaddr, port, num):
        self.ipaddr = ipaddr
        self.port = port
        self.num = num

    def server_link(self, conn, addr):
        global radar
        global connect_state
        global buf_data
        connect_state = 1
        print("5200，网关已经连接到服务器", flush=True)
        radar = conn
        while True:
            try:
                data = radar.recv(1024 * 8)
                if data:
                    print("接收到的截面线数据长度为", len(data), flush=True)
                    if len(buf_data) >= buf_data_threshold:
                        print("缓冲区已满，丢弃数据", flush=True)
                        continue
                    buf_data.extend(data)
                    # print("L", len(data), flush=True)

                    # print("from {0}:".format(addr), data.decode('utf-8'))
                    # print("L", len(data), flush=True)
                    # buf_data.extend(data)
                    # conn.send("Yes sir!".encode())
                else:
                    break
            except Exception:
                break
        conn.close()
        connect_state = 0
        # else:
        # print('没有接收到口令',flush=True)
        # conn.send("commend error".encode())
        # conn.close()
        # connect_state = 0

    def server_start(self):
        s_pro = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 65)

        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

        s_pro.bind((self.ipaddr, self.port))
        s_pro.listen(self.num)
        print('Waiting link...', flush=True)
        while True:
            conn, addr = s_pro.accept()
            print("Success connect from ", conn, flush=True)
            # conn.send(b'\x01\x02\x03\x04\x05\06\x07\x08')
            p = threading.Thread(target=self.server_link, args=(conn, addr))
            p.daemon = True
            p.start()

    def send_data(self, data, radar):
        radar.send(data)


# -------------------------------------------------------------------------------------------------------------------------
class ServerThread5300:  # 用于启动tcp/ip服务端来接收雷达数据，启用保活功能，设置大缓存来保证大数据传输

    def __init__(self, ipaddr, port, num):
        self.ipaddr = ipaddr
        self.port = port
        self.num = num

    def server_link(self, conn, addr):
        global radar5300
        global connect_state5300
        # if (conn.recv(65636)).decode('utf-8') == '12345678':
        connect_state5300 = 1
        print("5300，网关已经连接到服务器", flush=True)
        radar5300 = conn
        while True:
            try:
                data = radar5300.recv(1024 * 8)
                if data:
                    # print("from {0}:".format(addr), data.decode('utf-8'))
                    print("5300端口L", len(data), flush=True)
                    buf_data5300.extend(data)
                    # conn.send("Yes sir!".encode())
                else:
                    break
            except Exception:
                break
        conn.close()
        connect_state5300 = 0
        # else:
        # print('没有接收到口令',flush=True)
        # conn.send("commend error".encode())
        # conn.close()
        # connect_state = 0

    def server_start(self):
        s_pro = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 65)

        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

        s_pro.bind((self.ipaddr, self.port))
        s_pro.listen(self.num)
        print('Waiting link...', flush=True)
        while True:
            conn, addr = s_pro.accept()
            print("Success connect from ", conn, flush=True)
            # conn.send(b'\x01\x02\x03\x04\x05\06\x07\x08')
            p = threading.Thread(target=self.server_link, args=(conn, addr))
            p.daemon = True
            p.start()

    def send_data5300(self, data, radar5300):
        radar5300.send(data)


# -------------------------------------------------------------------------------------------------------------------------


# -------------------------------------------------------------------------------------------------------------------------
class ServerThread5400:  # 用于启动tcp/ip服务端来接收雷达数据，启用保活功能，设置大缓存来保证大数据传输

    def __init__(self, ipaddr, port, num):
        self.ipaddr = ipaddr
        self.port = port
        self.num = num

    def server_link(self, conn, addr):
        global radar5400
        global connect_state5400
        # if (conn.recv(65636)).decode('utf-8') == '12345678':
        connect_state5400 = 1
        print("5400，网关已经连接到服务器", flush=True)
        radar5400 = conn
        while True:
            try:
                data = radar5400.recv(1024 * 8)
                if data:

                    # print("from {0}:".format(addr), data.decode('utf-8'))
                    print("5400端口L", len(data), flush=True)
                    buf_data5400.extend(data)
                    print(buf_data5400)

                    # conn.send("Yes sir!".encode())
                else:
                    break
            except Exception:
                break
        conn.close()
        connect_state5400 = 0
        # else:
        # print('没有接收到口令',flush=True)
        # conn.send("commend error".encode())
        # conn.close()
        # connect_state = 0

    def server_start(self):
        s_pro = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 65)

        s_pro.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
        s_pro.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

        s_pro.bind((self.ipaddr, self.port))
        s_pro.listen(self.num)
        print('Waiting link...', flush=True)
        while True:
            conn, addr = s_pro.accept()
            print("Success connect from ", conn, flush=True)
            # conn.send(b'\x01\x02\x03\x04\x05\06\x07\x08')
            p = threading.Thread(target=self.server_link, args=(conn, addr))
            p.daemon = True
            p.start()

    def send_data5400(self, data, radar5400):
        radar5400.send(data)


e_num = a_num = v_num = None


# 提取并清空函数
def extract_and_clear():
    global buf_data5400, e_num, a_num, v_num

    data_str = buf_data5400.decode('utf-8', errors='ignore')

    # 提取数字
    electricity = re.search(r'Electricity: (\d+)%', data_str)
    alarm = re.search(r'Alarm: (\d+)', data_str)
    voltage = re.search(r'voltage: ([\d.]+)V', data_str)

    if electricity and alarm and voltage:
        e_num = int(electricity.group(1))
        a_num = int(alarm.group(1))
        v_num = float(voltage.group(1))
        print("提取结果 -> 电量:", e_num, "% 报警:", a_num, "电压:", v_num, "V")
    else:
        print("未能成功提取三项数据")

    # 清空数据
    buf_data5400.clear()

    # 每5秒重复执行
    threading.Timer(30, extract_and_clear).start()


extract_and_clear()


# -------------------------------------------------------------------------------------------------------------------------


def connect_sever():
    global buf_data
    ip_address = '192.168.1.200'
    ip_port = 29172
    first_marge_buff = bytearray()
    total_parse_size = 65636  # 65636#16777316

    # 创建一个socket对象
    client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 设置连接超时时间（秒）
    client_tcp_socket.settimeout(10)
    try:
        # 尝试连接到雷达IP地址和端口
        client_tcp_socket.connect((ip_address, ip_port))
    except socket.timeout:
        print("连接超时")
        # 可以在这里处理连接超时的情况
    except socket.error as e:
        print(f"连接错误: {e}")
        # 可以在这里处理其他socket错误
    else:
        print("连接成功")
        while True:
            response = client_tcp_socket.recv(65636)  # 如果没有指定或者为0，那么会接收所有可用的数据，直到达到系统缓冲区的大小限制
            if not response:
                # 如果没有数据，可能连接已经关闭
                break
            # save_data_to_file(response)

            # 数据流控制
            if len(buf_data) >= buf_data_threshold:
                print("缓冲区已满，丢弃数据", flush=True)
                continue
            buf_data.extend(response)
            # 如果一段时间内没有接收到数据，认为连接断开，重新连接
            if time.time() - last_received_time > 30:  # 超过30秒未收到数据
                print("超过30秒未接收到数据，正在重新连接...")
                break


def start_server():  # 启动flask框架线程
    app1.run(host='0.0.0.0')


# 线程存储
threads = {}
threads_lock = threading.Lock()
WATCHDOG_INTERVAL = 600000  # 看门狗检测间隔


def watchdog():
    """监控关键线程是否存活，若发现异常，则重启线程"""
    global threads

    while True:
        with threads_lock:  # 确保线程安全
            # 检查 TCP/IP 服务器线程
            if "tcp_ip_server" in threads and not threads["tcp_ip_server"].is_alive():
                print("[看门狗] TCP/IP 服务器线程已停止，正在重启...", flush=True)
                server = ServerThread('', 5200, 5)
                threads["tcp_ip_server"] = threading.Thread(target=server.server_start, daemon=True)
                threads["tcp_ip_server"].start()

            # 检查 矩阵处理线程
            if "up_data_matrix" in threads and not threads["up_data_matrix"].is_alive():
                print("[看门狗] 矩阵处理线程已停止，正在重启...", flush=True)
                threads["up_data_matrix"] = threading.Thread(target=run_up_data_thread, daemon=True)
                threads["up_data_matrix"].start()

            # 检查 时间处理线程
            if "time" in threads and not threads["time"].is_alive():
                print("[看门狗] 时间处理线程已停止，正在重启...", flush=True)
                threads["time"] = threading.Thread(target=run_time_thread, daemon=True)
                threads["time"].start()
            # 检查 up_data_thread
            if "up_data_thread" in threads and not threads["up_data_thread"].is_alive():
                print("[看门狗] up_data_thread 已停止，正在重启...", flush=True)
                threads["up_data_thread"] = threading.Thread(target=up_data_thread, daemon=True)
                threads["up_data_thread"].start()

            # # 检查连接线程（即 connect_sever）
            # if "connect_sever_thread" in threads and not threads["connect_sever_thread"].is_alive():
            #     print("[看门狗] connect_sever 线程已停止，正在重启...", flush=True)
            #     threads["connect_sever_thread"] = threading.Thread(target=connect_sever, daemon=True)
            #     threads["connect_sever_thread"].start()

        # 异步检查 Flask API
        threading.Thread(target=check_flask_api, daemon=True).start()

        time.sleep(WATCHDOG_INTERVAL)


def check_flask_api():
    """检查 Flask API 是否存活"""
    try:
        response = requests.get("http://127.0.0.1:5001/api/get_matrix", timeout=3)
        if response.status_code != 200:
            print("[看门狗] Flask API 可能失去响应", flush=True)
    except requests.RequestException:
        print("[看门狗] 无法访问 Flask API", flush=True)


# if __name__ == '__main__':

#     server = ServerThread('', 5200, 5)
#     tcp_ip_server = threading.Thread(target=server.server_start)
#     tcp_ip_server.daemon = True
#     tcp_ip_server.start()  # 启动tcp/ip服务端线程
#     print('tcp/ip已启动')

#     # client = threading.Thread(target=connect_sever())
#     # client.daemon = True
#     # client.start()
#     # print('客户端已启动')

#     up_data_martix = threading.Thread(target=run_up_data_thread)
#     up_data_martix.daemon = True
#     up_data_martix.start()  # 启动矩阵处理线程
#     print('矩阵处理已启动')

#     timeee = threading.Thread(target=run_time_thread)
#     timeee.daemon = True
#     timeee.start()  # 启动矩阵处理线程
#     print('时间已启动')

#     app1.run(host='0.0.0.0', port=5001)
#     # server_thread = threading.Thread(target=start_server)  # web线程
#     # server_thread.start()  #启动web线程
if __name__ == '__main__':
    with threads_lock:
        # 启动 TCP/IP 服务器线程
        server = ServerThread('', 5200, 5)
        threads["tcp_ip_server"] = threading.Thread(target=server.server_start, daemon=True)
        threads["tcp_ip_server"].start()
        print("TCP/IP 服务器已启动")

        server_5300 = ServerThread5300('', 5300, 5)
        tcp_ip_server_5300 = threading.Thread(target=server_5300.server_start)
        # tcp_ip_server_5300.daemon = True
        tcp_ip_server_5300.start()  # 启动tcp/ip服务端线程
        print('5300tcp/ip已启动')

        server_5400 = ServerThread5400('', 5400, 5)
        tcp_ip_server_5400 = threading.Thread(target=server_5400.server_start)
        # tcp_ip_server_5300.daemon = True
        tcp_ip_server_5400.start()  # 启动tcp/ip服务端线程
        print('5400tcp/ip已启动')

        # # 启动连接服务器线程
        # threads["connect_sever_thread"] = threading.Thread(target=connect_sever, daemon=True)
        # threads["connect_sever_thread"].start()
        # print("连接服务器线程已启动")

        # 启动矩阵处理线程
        threads["up_data_matrix"] = threading.Thread(target=run_up_data_thread, daemon=True)
        threads["up_data_matrix"].start()
        print("矩阵处理线程已启动")

        # 启动时间处理线程
        threads["time"] = threading.Thread(target=run_time_thread, daemon=True)
        threads["time"].start()
        print("时间处理线程已启动")

        # 启动 up_data_thread 线程
        threads["up_data_thread"] = threading.Thread(target=up_data_thread, daemon=True)
        threads["up_data_thread"].start()
        print("up_data_thread 已启动")

        threads["periodic_upload"] = threading.Thread(target=periodic_db_upload, daemon=True)
        threads["periodic_upload"].start()
        print("定时数据库上传线程已启动")

        # threads["periodic_upload2"] = threading.Thread(target=periodic_db_upload2, daemon=True)
        # threads["periodic_upload2"].start()
        # print("定时数据库2上传线程已启动")

        # 启动看门狗线程
        threads["watchdog"] = threading.Thread(target=watchdog, daemon=True)
        threads["watchdog"].start()
        print("看门狗线程已启动")

    # 启动 Flask，threaded=True 让其不会阻塞主线程
    app1.run(host='0.0.0.0', port=5001, threaded=True)

    # server_thread = threading.Thread(target=start_server)  # web线程
    # server_thread.start()  #启动web线程
