import pandas as pd
import matplotlib.pyplot as plt
from tkinter import Tk
from tkinter.filedialog import askopenfilename
import numpy as np

# ========================
# 去异常函数
# ========================
def remove_outliers(series, name,n_sigma=3):
    mean = series.mean()
    std = series.std()
    mask = (series > mean - n_sigma * std) & (series < mean + n_sigma * std)

    filtered = series[mask]
    outliers = series[~mask]

    # 打印异常值
    if len(outliers) > 0:
        print(f"\n{name} 异常值（共 {len(outliers)} 个）:")
        for idx, val in outliers.items():
            print(f"  index={idx}, value={val}")
    else:
        print(f"\n{name} 无异常值")

    return filtered

# ========================
# 选择文件
# ========================
def choose_excel():
    Tk().withdraw()
    return askopenfilename(
        title="请选择 Excel 文件",
        filetypes=[("Excel 文件", "*.xlsx;*.xls")]
    )

file_path = choose_excel()
if not file_path:
    print("未选择文件")
    exit()

# ========================
# 读取数据
# ========================
df = pd.read_excel(file_path)

# 只保留有效数据
df = df[df['mpu_isValid'] == 1]

# 原始数据
accel_x = df['mpu_accelX']
accel_y = df['mpu_accelY']
accel_z = df['mpu_accelZ']

gyro_x = df['mpu_gyroX']
gyro_y = df['mpu_gyroY']
gyro_z = df['mpu_gyroZ']

x_raw = range(len(df))

# ========================
# 图1：原始加速度
# ========================
plt.figure()
plt.plot(x_raw, accel_x, label='accel_x')
plt.plot(x_raw, accel_y, label='accel_y')
plt.plot(x_raw, accel_z, label='accel_z')
plt.title('Acceleration (Raw)')
plt.xlabel('Frame')
plt.ylabel('mg')
plt.legend()
plt.grid()

# ========================
# 图2：原始角速度
# ========================
plt.figure()
plt.plot(x_raw, gyro_x, label='gyro_x')
plt.plot(x_raw, gyro_y, label='gyro_y')
plt.plot(x_raw, gyro_z, label='gyro_z')
plt.title('Gyroscope (Raw)')
plt.xlabel('Frame')
plt.ylabel('mdps')
plt.legend()
plt.grid()

# ========================
# 去异常
# ========================
accel_x_f = remove_outliers(accel_x, "accel_x")
accel_y_f = remove_outliers(accel_y, "accel_y")
accel_z_f = remove_outliers(accel_z, "accel_z")

gyro_x_f = remove_outliers(gyro_x, "gyro_x")
gyro_y_f = remove_outliers(gyro_y, "gyro_y")
gyro_z_f = remove_outliers(gyro_z, "gyro_z")

# 对齐长度
min_len = min(len(accel_x_f), len(accel_y_f), len(accel_z_f),
              len(gyro_x_f), len(gyro_y_f), len(gyro_z_f))

accel_x_f = accel_x_f.iloc[:min_len]
accel_y_f = accel_y_f.iloc[:min_len]
accel_z_f = accel_z_f.iloc[:min_len]

gyro_x_f = gyro_x_f.iloc[:min_len]
gyro_y_f = gyro_y_f.iloc[:min_len]
gyro_z_f = gyro_z_f.iloc[:min_len]

x_f = range(min_len)

# ========================
# 平均值（去异常后）
# ========================
print("加速度平均值：",
      accel_x_f.mean(), accel_y_f.mean(), accel_z_f.mean())

print("角速度平均值：",
      gyro_x_f.mean(), gyro_y_f.mean(), gyro_z_f.mean())

# ========================
# 图3：去异常后加速度
# ========================
plt.figure()
plt.plot(x_f, accel_x_f, label='accel_x')
plt.plot(x_f, accel_y_f, label='accel_y')
plt.plot(x_f, accel_z_f, label='accel_z')
plt.title('Acceleration (Filtered)')
plt.xlabel('Frame')
plt.ylabel('mg')
plt.legend()
plt.grid()

# ========================
# 图4：去异常后角速度
# ========================
plt.figure()
plt.plot(x_f, gyro_x_f, label='gyro_x')
plt.plot(x_f, gyro_y_f, label='gyro_y')
plt.plot(x_f, gyro_z_f, label='gyro_z')
plt.title('Gyroscope (Filtered)')
plt.xlabel('Frame')
plt.ylabel('mdps')
plt.legend()
plt.grid()

# ========================
# 显示
# ========================
plt.show()

