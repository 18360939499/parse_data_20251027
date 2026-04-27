import pandas as pd
import matplotlib.pyplot as plt
from tkinter import Tk
from tkinter.filedialog import askopenfilename
import numpy as np

def remove_outliers(series, n_sigma=3):
    mean = series.mean()
    std = series.std()
    return series[(series > mean - n_sigma * std) & (series < mean + n_sigma * std)]

# 1. 选择Excel文件
def choose_excel():
    Tk().withdraw()  # 隐藏主窗口
    file_path = askopenfilename(
        title="请选择 Excel 文件",
        filetypes=[("Excel 文件", "*.xlsx;*.xls")]
    )
    return file_path

# 2. 主流程
file_path = choose_excel()
if not file_path:
    print("未选择文件")
    exit()

# 读取数据
df = pd.read_excel(file_path)

# 数据过滤:只保留有效数据
df = df[df['mpu_isValid'] == 1]

# 取数据列
accel_x = df['mpu_accelX']
accel_y = df['mpu_accelY']
accel_z = df['mpu_accelZ']

gyro_x = df['mpu_gyroX']
gyro_y = df['mpu_gyroY']
gyro_z = df['mpu_gyroZ']

# 横坐标（帧序号）
x = range(len(df))

# ========================
# 3. 画加速度
# ========================
plt.figure()
plt.plot(x, accel_x, label='accel_x')
plt.plot(x, accel_y, label='accel_y')
plt.plot(x, accel_z, label='accel_z')

plt.title('Acceleration Trend')
plt.xlabel('Frame')
plt.ylabel('mg')
plt.legend()
plt.grid()

# ========================
# 4. 画角速度
# ========================
plt.figure()
plt.plot(x, gyro_x, label='gyro_x')
plt.plot(x, gyro_y, label='gyro_y')
plt.plot(x, gyro_z, label='gyro_z')

plt.title('Gyroscope Trend')
plt.xlabel('Frame')
plt.ylabel('mdps')
plt.legend()
plt.grid()

# 显示
plt.show()


