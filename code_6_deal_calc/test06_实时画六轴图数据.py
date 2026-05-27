import os
import struct
import matplotlib.pyplot as plt
from collections import deque
from tkinter import Tk
from tkinter.filedialog import askdirectory

# ===============================
# 配置
# ===============================
start_flag = bytes.fromhex("05 00 00 00")
flagLength = 0xCA4

MAX_POINTS = 10000   # 图中最多显示多少点

# ===============================
# 选择文件夹
# ===============================
def choose_folder():
    Tk().withdraw()
    folder = askdirectory(title="请选择BIN文件夹")
    if not folder:
        raise ValueError("未选择文件夹")
    return folder

# ===============================
# 初始化缓存
# ===============================
accelX = deque(maxlen=MAX_POINTS)
accelY = deque(maxlen=MAX_POINTS)
accelZ = deque(maxlen=MAX_POINTS)

gyroX = deque(maxlen=MAX_POINTS)
gyroY = deque(maxlen=MAX_POINTS)
gyroZ = deque(maxlen=MAX_POINTS)

# ===============================
# 初始化绘图
# ===============================
plt.ion()

fig1, ax1 = plt.subplots(figsize=(12,6))
fig2, ax2 = plt.subplots(figsize=(12,6))

# 加速度曲线
line_ax, = ax1.plot([], [], label="accelX")
line_ay, = ax1.plot([], [], label="accelY")
line_az, = ax1.plot([], [], label="accelZ")

ax1.set_title("Accelerometer")
ax1.set_xlabel("Frame")
ax1.set_ylabel("Value")
ax1.legend()
ax1.grid(True)

# 陀螺仪曲线
line_gx, = ax2.plot([], [], label="gyroX")
line_gy, = ax2.plot([], [], label="gyroY")
line_gz, = ax2.plot([], [], label="gyroZ")

ax2.set_title("Gyroscope")
ax2.set_xlabel("Frame")
ax2.set_ylabel("Value")
ax2.legend()
ax2.grid(True)

# ===============================
# 更新图像
# ===============================
def update_plot():

    x1 = range(len(accelX))
    x2 = range(len(gyroX))

    line_ax.set_data(x1, accelX)
    line_ay.set_data(x1, accelY)
    line_az.set_data(x1, accelZ)

    line_gx.set_data(x2, gyroX)
    line_gy.set_data(x2, gyroY)
    line_gz.set_data(x2, gyroZ)

    ax1.relim()
    ax1.autoscale_view()

    ax2.relim()
    ax2.autoscale_view()

    fig1.canvas.draw()
    fig1.canvas.flush_events()

    fig2.canvas.draw()
    fig2.canvas.flush_events()

# ===============================
# 解析BIN文件
# ===============================
def parse_bin(file_path):

    with open(file_path, "rb") as f:
        content = f.read()

    start = 0

    while True:

        start_index = content.find(start_flag, start)

        if start_index == -1:
            break

        # 数据长度
        data_length = struct.unpack(
            '<I',
            content[start_index + 4:start_index + 8]
        )[0]

        # 校验长度
        if data_length != flagLength:
            start = start_index + 1
            continue

        data_start = start_index + len(start_flag) + 4
        data_end = data_start + data_length

        if data_end > len(content):
            break

        data_bytes = content[data_start:data_end]

        # =========================
        # 解析 float 数据
        # =========================
        data_part1 = []

        for i in range(36, (36 + 7 * 4 * 100), 4):

            value = struct.unpack(
                '<f',
                data_bytes[i:i + 4]
            )[0]

            data_part1.append(value)

        # =========================
        # 提取 MPU 数据
        # 每100个点一组
        # =========================

        accelX.extend(data_part1[0:100])
        accelY.extend(data_part1[100:200])
        accelZ.extend(data_part1[200:300])

        gyroX.extend(data_part1[300:400])
        gyroY.extend(data_part1[400:500])
        gyroZ.extend(data_part1[500:600])

        # 更新图像
        update_plot()

        # 下一个包
        start = data_end

# ===============================
# 主程序
# ===============================
input_folder = choose_folder()

for file_name in os.listdir(input_folder):

    if file_name.lower().endswith(".bin"):

        file_path = os.path.join(input_folder, file_name)

        print(f"正在解析: {file_name}")

        parse_bin(file_path)

print("解析完成")

plt.ioff()
plt.show()