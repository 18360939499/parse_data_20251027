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
# 读取Excel文件
# =========================
file_path = choose_excel()
if not file_path:
    print("未选择文件")
    exit()

df = pd.read_excel(file_path)

# =========================
# 自动按列名提取
# =========================
accelX_cols = [c for c in df.columns if "accelX_" in c]
accelY_cols = [c for c in df.columns if "accelY_" in c]
accelZ_cols = [c for c in df.columns if "accelZ_" in c]

gyroX_cols = [c for c in df.columns if "gyroX_" in c]
gyroY_cols = [c for c in df.columns if "gyroY_" in c]
gyroZ_cols = [c for c in df.columns if "gyroZ_" in c]

# =========================
# 求平均曲线
# =========================
accelX_mean = df[accelX_cols].mean(axis=0).values
accelY_mean = df[accelY_cols].mean(axis=0).values
accelZ_mean = df[accelZ_cols].mean(axis=0).values

gyroX_mean = df[gyroX_cols].mean(axis=0).values
gyroY_mean = df[gyroY_cols].mean(axis=0).values
gyroZ_mean = df[gyroZ_cols].mean(axis=0).values


# =========================
# 输出整体平均值
# =========================
print("平均值统计：")

print(f"accelX 平均值: {df[accelX_cols].values.mean():.6f}")
print(f"accelY 平均值: {df[accelY_cols].values.mean():.6f}")
print(f"accelZ 平均值: {df[accelZ_cols].values.mean():.6f}")

print(f"gyroX 平均值: {df[gyroX_cols].values.mean():.6f}")
print(f"gyroY 平均值: {df[gyroY_cols].values.mean():.6f}")
print(f"gyroZ 平均值: {df[gyroZ_cols].values.mean():.6f}")


# =========================
# 图1：加速度
# =========================
plt.figure(figsize=(12,6))

plt.plot(accelX_mean, label="accelX")
plt.plot(accelY_mean, label="accelY")
plt.plot(accelZ_mean, label="accelZ")

plt.title("Accelerometer Data")
plt.xlabel("Sample Index")
plt.ylabel("Value")
plt.legend()
plt.grid(True)

# =========================
# 图2：角速度
# =========================
plt.figure(figsize=(12,6))

plt.plot(gyroX_mean, label="gyroX")
plt.plot(gyroY_mean, label="gyroY")
plt.plot(gyroZ_mean, label="gyroZ")

plt.title("Gyroscope Data")
plt.xlabel("Sample Index")
plt.ylabel("Value")
plt.legend()
plt.grid(True)

# =========================
# 显示图像
# =========================
plt.show()