import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from tkinter import Tk
from tkinter.filedialog import askopenfilename


def choose_excel():
    Tk().withdraw()
    return askopenfilename(
        title="请选择 Excel 文件",
        filetypes=[("Excel 文件", "*.xlsx;*.xls")]
    )


# =========================
# 读取Excel
# =========================
file_path = choose_excel()
if not file_path:
    print("未选择文件")
    exit()

df = pd.read_excel(file_path)

# =========================
# 自动匹配列
# =========================
accelX_cols = [c for c in df.columns if "accelX_" in c]
accelY_cols = [c for c in df.columns if "accelY_" in c]
accelZ_cols = [c for c in df.columns if "accelZ_" in c]

gyroX_cols = [c for c in df.columns if "gyroX_" in c]
gyroY_cols = [c for c in df.columns if "gyroY_" in c]
gyroZ_cols = [c for c in df.columns if "gyroZ_" in c]

# =========================
# 把所有 frame 按顺序拼接成一整条曲线
# =========================
accelX_all = []
accelY_all = []
accelZ_all = []

gyroX_all = []
gyroY_all = []
gyroZ_all = []

# 逐行读取每个 frame，并把数据追加到列表里
for _, row in df.iterrows():
    accelX_all.extend(row[accelX_cols].values)
    accelY_all.extend(row[accelY_cols].values)
    accelZ_all.extend(row[accelZ_cols].values)

    gyroX_all.extend(row[gyroX_cols].values)
    gyroY_all.extend(row[gyroY_cols].values)
    gyroZ_all.extend(row[gyroZ_cols].values)

# =========================
# 图1：加速度 3轴 拼接成 3条连续折线（同一张图）
# =========================
plt.figure(figsize=(14, 6))
plt.plot(accelX_all, label="accelX")
plt.plot(accelY_all, label="accelY")
plt.plot(accelZ_all, label="accelZ")
plt.title("accel")
plt.xlabel("sample point")
plt.ylabel("accel")
plt.legend()
plt.grid(True)

# =========================
# 图2：陀螺仪 3轴 拼接成 3条连续折线（同一张图）
# =========================
plt.figure(figsize=(14, 6))
plt.plot(gyroX_all, label="gyroX")
plt.plot(gyroY_all, label="gyroY")
plt.plot(gyroZ_all, label="gyroZ")
plt.title("gyro")
plt.xlabel("sample point")
plt.ylabel("gyro")
plt.legend()
plt.grid(True)

plt.show()